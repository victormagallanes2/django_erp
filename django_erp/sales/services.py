# sales/services.py - VERSIÓN COMPLETA CON CREACIÓN DE FACTURA
from django.db import transaction
from django.core.exceptions import ValidationError
from django.apps import apps
from .models import SaleOrder
from django.db.models import Sum
from django.db.models.functions import TruncDay, TruncMonth, TruncYear
from django.utils import timezone
from decimal import Decimal
from datetime import timedelta, datetime
from django_erp.configuration.models import Company
import logging
from .models import SaleOrder, SaleInvoice
from decimal import Decimal, ROUND_HALF_UP


logger = logging.getLogger(__name__)



class SaleService:
    """Servicios de ventas - Flujo completo con Notas de Entrega y Facturas"""
    
    @staticmethod
    @transaction.atomic
    def confirm_order(order, user=None):
        """
        ✅ Confirmar una orden de venta.
        - Crea una Nota de Entrega en Borrador para productos físicos
        - Registra servicios como confirmados
        - No reduce stock hasta que el almacenista confirme la nota
        """
        from django_erp.inventory.models import DeliveryNote, DeliveryNoteLine, Location
        
        company = order.company or Company.get_active()
        if not company:
            raise ValidationError("No hay una compañía asociada a esta orden o activa.")
        
        logger.info("=" * 80)
        logger.info(f"🔴 [confirm_order] Confirmando orden {order.number}")
        logger.info(f"   Compañía: {company.code}")
        
        # ============================================================
        # 📦 1. CREAR NOTA DE ENTREGA EN BORRADOR (para productos físicos)
        # ============================================================
        
        existing_note = DeliveryNote.objects.filter(
            customer=order.customer,
            customer_name=order.customer.name,
            notes__icontains=f"Venta {order.number}",
            company=company
        ).first()
        
        if existing_note:
            logger.info(f"   ℹ️ Ya existe una nota de entrega para esta orden: {existing_note.number}")
        else:
            delivery_note = DeliveryNote.objects.create(
                customer=order.customer,
                customer_name=order.customer.name,
                notes=f"Venta {order.number} - {order.customer.name}",
                status='DRAFT',
                user=user or order.user,
                company=company,
            )
            logger.info(f"   ✅ Nota de entrega creada: {delivery_note.number}")
            
            lines_created = 0
            for line in order.lines.all():
                if line.product and not line.product.is_service:
                    location = line.location
                    if not location:
                        location = Location.objects.filter(
                            company=company,
                            is_active=True
                        ).first()
                        
                        if not location:
                            location = Location.objects.create(
                                code=f"ALM-{company.code}",
                                name=f"Almacén Principal - {company.name}",
                                description=f"Almacén principal de {company.name}",
                                company=company,
                                is_active=True
                            )
                            logger.info(f"   ✅ Ubicación por defecto creada: {location.code}")
                    
                    if not location:
                        logger.error(f"   ❌ No hay ubicación para el producto {line.product.name}")
                        raise ValidationError(
                            f"No hay ubicación para el producto {line.product.name} en {company.code}"
                        )
                    
                    DeliveryNoteLine.objects.create(
                        note=delivery_note,
                        product=line.product,
                        location=location,
                        quantity=line.quantity,
                        company=company,
                    )
                    lines_created += 1
                    logger.info(f"   ✅ Línea {lines_created}: {line.product.name} x {line.quantity} en {location.code}")
                elif line.product and line.product.is_service:
                    logger.info(f"   📝 Servicio confirmado: {line.product.name}")
                else:
                    logger.info(f"   📝 Servicio confirmado: {line.product_name or line.description or 'Servicio'}")
            
            if lines_created == 0:
                logger.info("   ℹ️ No hay productos físicos en la orden, no se crearon líneas en la nota")
                delivery_note.status = 'CANCELLED'
                delivery_note.save()
                logger.info("   ℹ️ Nota de entrega cancelada (no hay productos físicos)")
            else:
                logger.info(f"   📊 Total líneas creadas: {lines_created}")
        
        # ============================================================
        # ✅ 2. ACTUALIZAR ESTADO DE LA ORDEN
        # ============================================================
        
        order.status = 'CONFIRMED'
        order.confirmed_date = timezone.now()
        order.save()
        
        logger.info(f"   ✅ Orden {order.number} marcada como CONFIRMADA")
        
        logger.info("=" * 80)
        return order
    
    @staticmethod
    @transaction.atomic
    def deliver_order(order, user=None):
        """
        ✅ Entregar una orden (llamado desde la confirmación de la nota de entrega).
        - Marca la orden como DELIVERED
        - Genera la factura de venta
        - Registra la transacción en caja (SOLO UNA VEZ)
        - Asocia los pagos existentes a la factura
        """
        from .models import SaleInvoice, SaleInvoiceLine, Payment
        from .models import CashTransaction
        from .helpers import get_open_register
        from django_erp.configuration.models import PaymentMethod, Currency
        
        logger.info("=" * 80)
        logger.info(f"🔴 [deliver_order] Entregando orden {order.number}")
        
        if order.status != 'CONFIRMED':
            logger.warning(f"   ⚠️ La orden no está confirmada (estado: {order.status})")
            raise ValidationError("Solo se pueden entregar órdenes confirmadas.")
        
        if order.status == 'DELIVERED':
            logger.info(f"   ℹ️ La orden ya estaba entregada")
            return order
        
        company = order.company or Company.get_active()
        
        # ============================================================
        # 💰 1. REGISTRAR TRANSACCIÓN EN CAJA (SOLO UNA VEZ)
        # ============================================================
        transaction_created = False
        if order.total > 0:
            try:
                register = get_open_register(user or order.user)
                
                # ✅ Verificar que no exista ya una transacción para esta orden
                existing_transaction = CashTransaction.objects.filter(
                    reference=order.number,
                    type='SALE',
                    register=register
                ).first()
                
                if not existing_transaction:
                    transaction = CashTransaction.objects.create(
                        register=register,
                        type='SALE',
                        amount=order.total,
                        description=f"Venta {order.number} - {order.customer.name}",
                        reference=order.number,
                        user=user or order.user,
                        company=company,
                    )
                    register.calculate_totals()
                    transaction_created = True
                    logger.info(f"   ✅ Transacción registrada en caja {register.number}")
                else:
                    logger.info(f"   ℹ️ Transacción ya existe para {order.number}")
                    transaction = existing_transaction
                    transaction_created = False
                    
            except ValidationError as e:
                logger.warning(f"   ⚠️ Error al registrar en caja: {e}")
                # Si no hay caja abierta, no se puede registrar transacción
                transaction = None
        
        # ============================================================
        # ✅ 2. MARCAR COMO ENTREGADA
        # ============================================================
        order.status = 'DELIVERED'
        order.delivered_date = timezone.now()
        order.save()
        logger.info(f"   ✅ Orden {order.number} marcada como DELIVERED")
        
        # ============================================================
        # 📄 3. GENERAR FACTURA DE VENTA
        # ============================================================
        try:
            # ✅ Verificar si ya existe factura para esta orden
            existing_invoice = SaleInvoice.objects.filter(
                sale_order=order,
                company=company
            ).first()
            
            if existing_invoice:
                logger.info(f"   ℹ️ Ya existe factura {existing_invoice.number} para esta orden")
                return order
            
            # ✅ Generar número de factura
            from datetime import datetime
            last_invoice = SaleInvoice.objects.order_by('-id').first()
            if last_invoice and last_invoice.number:
                try:
                    last_num = int(last_invoice.number.split('-')[-1])
                    next_num = last_num + 1
                except (ValueError, IndexError):
                    next_num = 1
            else:
                next_num = 1
            
            number = f"FAC-VENTA-{datetime.now().strftime('%Y%m')}-{next_num:04d}"
            logger.info(f"   📝 Número de factura generado: {number}")
            
            from django_erp.accounting.services import TaxService
            tax_rate = TaxService.get_current_vat_rate(company) if company else Decimal('16.00')
            
            # ✅ Crear la factura
            invoice = SaleInvoice.objects.create(
                number=number,
                sale_order=order,
                customer=order.customer,
                customer_name=order.customer.name,
                customer_tax_id=order.customer.tax_id,
                customer_address=order.customer.address,
                date_due=datetime.now().date() + timedelta(days=30),
                status='ISSUED',
                tax_rate=tax_rate,
                user=user or order.user,
                sync_status='SYNCED',
                company=company,
            )
            logger.info(f"   ✅ Factura creada: {invoice.number}")
            
            # ✅ Copiar líneas de la orden a la factura
            lines_count = 0
            for sale_line in order.lines.all():
                SaleInvoiceLine.objects.create(
                    invoice=invoice,
                    sale_line=sale_line,
                    product=sale_line.product,
                    product_code=sale_line.product.code if sale_line.product else '',
                    product_name=sale_line.product.name if sale_line.product else sale_line.product_name or '',
                    description=sale_line.description,
                    quantity=sale_line.quantity,
                    unit_price=sale_line.unit_price,
                    subtotal=sale_line.subtotal,
                    company=company,
                )
                lines_count += 1
            
            logger.info(f"   ✅ {lines_count} líneas copiadas a la factura")
            
            # ✅ Calcular totales
            invoice.calculate_totals()
            invoice.save()
            logger.info(f"   ✅ Totales calculados: Subtotal={invoice.subtotal}, IVA={invoice.tax}, Total={invoice.total}")
            
            # ============================================================
            # 💰 4. ASOCIAR PAGOS A LA FACTURA
            # ============================================================
            payments_updated = 0
            
            # ✅ Si se creó una transacción, crear el pago desde ella
            if transaction_created and transaction:
                # Crear pago desde la transacción recién creada
                default_method = PaymentMethod.objects.filter(
                    company=company,
                    is_active=True
                ).first()
                
                if default_method:
                    Payment.objects.create(
                        sale_order=order,
                        sale_invoice=invoice,
                        method=default_method,
                        currency=Currency.objects.get(code='USD'),
                        amount=transaction.amount,
                        amount_usd=transaction.amount,
                        reference=f"Pago automático - {order.number}",
                        status='COMPLETED',
                        user=user or order.user,
                        company=company,
                    )
                    payments_updated += 1
                    logger.info(f"   ✅ Pago creado desde transacción")
            
            # ✅ Buscar pagos existentes que no tengan factura asignada
            payments = Payment.objects.filter(
                sale_order=order,
                status='COMPLETED',
                sale_invoice__isnull=True
            )
            
            logger.info(f"   💰 Pagos existentes sin factura: {payments.count()}")
            
            for payment in payments:
                payment.sale_invoice = invoice
                payment.save()
                payments_updated += 1
                logger.info(f"   ✅ Pago {payment.id} asociado a factura {invoice.number}")
            
            logger.info(f"   💰 Total pagos asociados: {payments_updated}")
            
            if payments_updated == 0:
                logger.warning("   ⚠️ No se encontraron pagos para asociar a la factura")
            
            # ✅ Agregar factura a la orden
            if hasattr(order, 'invoices') and order.invoices is not None:
                order.invoices.add(invoice)
            order.save()
            
            logger.info(f"   ✅ Factura asociada a la orden {order.number}")
            
        except Exception as e:
            logger.error(f"   ❌ Error al generar factura: {e}")
            import traceback
            logger.error(f"   Traceback: {traceback.format_exc()}")
            # No detener el proceso si falla la factura, solo registrar el error
        
        logger.info("=" * 80)
        return order
    
    @staticmethod
    @transaction.atomic
    def cancel_order(order, user=None):
        """Cancelar una orden"""
        if order.status in ['DELIVERED', 'CANCELLED']:
            raise ValidationError("No se puede cancelar una orden entregada o ya cancelada")
        
        order.status = 'CANCELLED'
        order.save()
        
        return order
    
    @staticmethod
    def can_transition(order, new_status, current_status=None):
        """Verificar si una transición de estado es válida."""
        valid_transitions = {
            'DRAFT': ['CONFIRMED', 'CANCELLED'],
            'CONFIRMED': ['DELIVERED', 'CANCELLED'],
            'DELIVERED': [],
            'CANCELLED': [],
        }
        
        status = current_status if current_status is not None else order.status
        return new_status in valid_transitions.get(status, [])


class SaleInvoiceService:
    """Servicio para facturas de venta"""
    
    @staticmethod
    @transaction.atomic
    def create_invoice_from_sale_order(sale_order_id, user=None):
        """
        Crear factura de venta desde una orden de venta entregada.
        """
        from .models import SaleInvoice, SaleInvoiceLine
        from datetime import datetime, timedelta
        from decimal import Decimal
        
        logger.info("=" * 80)
        logger.info("🔴 [create_invoice_from_sale_order] CREANDO FACTURA")
        logger.info(f"   sale_order_id: {sale_order_id}")
        
        try:
            sale_order = SaleOrder.objects.get(id=sale_order_id)
            logger.info(f"   ✅ Orden encontrada: {sale_order.number}")
            logger.info(f"   Estado: {sale_order.status}")
        except SaleOrder.DoesNotExist as e:
            logger.error(f"   ❌ Orden no encontrada: {e}")
            raise
        
        if sale_order.status != 'DELIVERED':
            logger.error(f"   ❌ La orden no está entregada (estado: {sale_order.status})")
            raise ValidationError("Solo se pueden facturar órdenes entregadas")
        
        # Verificar si ya existe factura
        existing = SaleInvoice.objects.filter(sale_order=sale_order).first()
        if existing:
            logger.warning(f"   ⚠️ Esta orden ya tiene una factura: {existing.number}")
            return existing
        
        company = sale_order.company
        if not company:
            logger.error("   ❌ No hay una empresa configurada para esta orden")
            raise ValidationError("No hay una empresa configurada para esta orden")
        
        logger.info(f"   Compañía: {company.code} - {company.name}")
        
        # Generar número de factura
        last_invoice = SaleInvoice.objects.order_by('-id').first()
        if last_invoice and last_invoice.number:
            try:
                last_num = int(last_invoice.number.split('-')[-1])
                next_num = last_num + 1
            except (ValueError, IndexError):
                next_num = 1
        else:
            next_num = 1
        
        number = f"FAC-VENTA-{datetime.now().strftime('%Y%m')}-{next_num:04d}"
        logger.info(f"   Número de factura generado: {number}")
        
        from django_erp.accounting.services import TaxService
        tax_rate = TaxService.get_current_vat_rate(company) if company else Decimal('16.00')
        
        invoice = SaleInvoice.objects.create(
            number=number,
            sale_order=sale_order,
            customer=sale_order.customer,
            customer_name=sale_order.customer.name,
            customer_tax_id=sale_order.customer.tax_id,
            customer_address=sale_order.customer.address,
            date_due=datetime.now().date() + timedelta(days=30),
            status='ISSUED',
            tax_rate=tax_rate,
            user=user or sale_order.user,
            sync_status='SYNCED',
            company=company,
        )
        logger.info(f"   ✅ Factura creada: {invoice.number}")
        
        # Copiar líneas
        lines_count = 0
        for line in sale_order.lines.all():
            SaleInvoiceLine.objects.create(
                invoice=invoice,
                sale_line=line,
                product=line.product,
                product_code=line.product.code if line.product else '',
                product_name=line.product.name if line.product else line.product_name or '',
                description=line.description,
                quantity=line.quantity,
                unit_price=line.unit_price,
                subtotal=line.subtotal,
                company=company,
            )
            lines_count += 1
        
        logger.info(f"   ✅ {lines_count} líneas copiadas a la factura")
        
        invoice.calculate_totals()
        invoice.save()
        logger.info(f"   ✅ Totales calculados: Subtotal={invoice.subtotal}, IVA={invoice.tax}, Total={invoice.total}")
        
        logger.info(f"✅ Factura de venta {invoice.number} creada")
        logger.info("=" * 80)
        return invoice


class SaleReportService:
    """Servicio para generar reportes de ventas."""

    @staticmethod
    def get_totals_by_period(period_type='day', days_back=30, company=None):
        """
        Obtiene el total de ventas agrupadas por un período específico.
        """
        queryset = SaleInvoice.objects.filter(status__in=['ISSUED', 'PAID'])
        if company:
            queryset = queryset.filter(company=company)
        else:
            company = Company.get_active()
            if company:
                queryset = queryset.filter(company=company)
        if period_type == 'day':
            start_date = timezone.now() - timedelta(days=days_back)
            queryset = queryset.filter(date_issued__gte=start_date)
            trunc_function = TruncDay('date_issued')
            label_format = '%d-%m'
        elif period_type == 'month':
            start_date = timezone.now() - timedelta(days=365)
            queryset = queryset.filter(date_issued__gte=start_date)
            trunc_function = TruncMonth('date_issued')
            label_format = 'b Y'
        elif period_type == 'year':
            start_date = timezone.now() - timedelta(days=3650)
            queryset = queryset.filter(date_issued__gte=start_date)
            trunc_function = TruncYear('date_issued')
            label_format = 'Y'
        else:
            raise ValueError("Tipo de período no soportado")

        report_data = (
            queryset
            .annotate(period=trunc_function)
            .values('period')
            .annotate(total=Sum('total'))
            .order_by('period')
        )

        labels = []
        totals = []

        for entry in report_data:
            if entry['period']:
                labels.append(entry['period'].strftime(label_format))
                totals.append(float(entry['total']))
            else:
                labels.append('Fecha desconocida')
                totals.append(0.0)

        return labels, totals

    @staticmethod
    def get_grand_totals(company=None):
        """
        Calcula los totales de ventas de hoy, este mes y este año.
        """
        today = timezone.now().date()
        first_day_of_month = today.replace(day=1)
        first_day_of_year = today.replace(month=1, day=1)

        queryset = SaleInvoice.objects.filter(status__in=['ISSUED', 'PAID'])

        if company:
            queryset = queryset.filter(company=company)
        else:
            company = Company.get_active()
            if company:
                queryset = queryset.filter(company=company)

        sales_today = queryset.filter(date_issued=today).aggregate(Sum('total'))['total__sum'] or Decimal('0.00')
        sales_this_month = queryset.filter(date_issued__gte=first_day_of_month).aggregate(Sum('total'))['total__sum'] or Decimal('0.00')
        sales_this_year = queryset.filter(date_issued__gte=first_day_of_year).aggregate(Sum('total'))['total__sum'] or Decimal('0.00')

        return {
            'today': float(sales_today),
            'this_month': float(sales_this_month),
            'this_year': float(sales_this_year),
        }


class SaleInvoiceProcessingService:

    
    @staticmethod
    @transaction.atomic
    def process_paid_invoice(invoice, user, request=None, skip_inventory=False):
        """
        Procesa una factura que acaba de pasar a estado PAID.
        
        Args:
            invoice: Instancia de SaleInvoice
            user: Usuario que realiza la acción
            request: Request opcional (para mensajes en admin)
            skip_inventory: Si True, no reduce inventario (útil si ya se hizo)
        
        Returns:
            dict con el resultado del procesamiento
        """
        from .models import CashTransaction, Payment
        from .helpers import get_open_register
        from django_erp.configuration.models import PaymentMethod, Currency
        from django_erp.inventory.models import Movement
        from django_erp.accounting.services import TaxService
        
        logger.info("=" * 80)
        logger.info(f"🔴 [SaleInvoiceProcessingService] Procesando factura {invoice.number}")
        
        result = {
            'invoice': invoice,
            'totals_recalculated': False,
            'commission_created': None,
            'cash_transaction_created': False,
            'payment_created': False,
            'inventory_reduced': False,
            'movements_created': 0,
            'errors': [],
            'warnings': [],
        }
        
        company = invoice.company or Company.get_active()
        if not company:
            raise ValidationError("No hay una compañía activa para procesar la factura.")
        
        # ============================================================
        # 1. RECALCULAR TOTALES
        # ============================================================
        try:
            invoice.refresh_from_db()
            
            subtotal = Decimal('0.00')
            for line in invoice.lines.all():
                subtotal += Decimal(str(line.subtotal))
            
            tax_rate = TaxService.get_current_vat_rate(company) if company else Decimal('16.00')
            tax = subtotal * (tax_rate / Decimal('100'))
            total = subtotal + tax
            
            invoice.subtotal = subtotal.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            invoice.tax = tax.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            invoice.total = total.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            invoice.tax_rate = tax_rate
            
            invoice.save(update_fields=['subtotal', 'tax', 'total', 'tax_rate'])
            invoice.refresh_from_db()
            
            result['totals_recalculated'] = True
            logger.info(f"   ✅ Totales: Subtotal={invoice.subtotal}, IVA={invoice.tax}, Total={invoice.total}")
        except Exception as e:
            logger.error(f"   ❌ Error recalculando totales: {e}")
            result['errors'].append(f"Error recalculando totales: {e}")
            raise
        
        # ============================================================
        # 2. GENERAR COMISIÓN (si aplica)
        # ============================================================
        try:
            from django_erp.rrhh.services import CommissionService

            # ✅ CRÍTICO: Refrescar la factura desde la BD para asegurar
            #    que salesperson_id y lines estén cargados correctamente
            invoice.refresh_from_db()
            
            logger.info("   🎯 [COMISIÓN] Iniciando generación de comisión")
            logger.info(f"      invoice.number: {invoice.number}")
            logger.info(f"      invoice.status: {invoice.status}")
            logger.info(f"      company.commission_enabled: {getattr(company, 'commission_enabled', 'N/A')}")
            logger.info(f"      company.commission_by_service_only: {getattr(company, 'commission_by_service_only', 'N/A')}")
            logger.info(f"      invoice.salesperson_id: {invoice.salesperson_id}")
            logger.info(f"      invoice.subtotal: {invoice.subtotal}")
            logger.info(f"      invoice.lines.count(): {invoice.lines.count()}")
            
            # ✅ Solo generar comisión si la factura está en estado PAID
            if invoice.status != 'PAID':
                logger.info(f"      ℹ️ Factura no está PAID (estado={invoice.status}), saltando comisión")
            else:
                # ✅ Calcular base ANTES de llamar al servicio
                base = CommissionService._calculate_commission_base(invoice)
                logger.info(f"      Base comisionable calculada: {base}")
                
                commission = CommissionService.create_commission_for_invoice(invoice)
                if commission:
                    result['commission_created'] = commission
                    logger.info(f"   ✅ Comisión generada: ${commission.amount:.2f} ({commission.rate}%)")
                else:
                    logger.warning("   ⚠️ CommissionService devolvió None (no se generó comisión)")
        except Exception as e:
            logger.error(f"   ❌ Error al generar comisión: {e}")
            import traceback
            logger.error(f"   Traceback: {traceback.format_exc()}")
            result['warnings'].append(f"Error al generar comisión: {e}")
        
        # ============================================================
        # 3. VERIFICAR MONTO VÁLIDO
        # ============================================================
        if invoice.total <= 0:
            msg = f"El total de la factura es {invoice.total}, no se registra en caja"
            logger.warning(f"   ⚠️ {msg}")
            result['warnings'].append(msg)
            return result
        
        # ============================================================
        # 4. REGISTRAR EN CAJA (con verificación de duplicados)
        # ============================================================
        cash_exists = CashTransaction.objects.filter(
            reference=invoice.number,
            type='SALE'
        ).exists()
        
        if cash_exists:
            logger.info(f"   ℹ️ Transacción de caja ya existe para {invoice.number}")
        else:
            try:
                register = get_open_register(user)
                logger.info(f"   ✅ Caja abierta: {register.number}")
                
                CashTransaction.objects.create(
                    register=register,
                    type='SALE',
                    amount=invoice.total,
                    description=f"Factura {invoice.number} - {invoice.customer_name}",
                    reference=invoice.number,
                    user=user,
                    company=invoice.company,
                )
                register.calculate_totals()
                
                result['cash_transaction_created'] = True
                logger.info(f"   ✅ Transacción creada: ${invoice.total:.2f}")
            except ValidationError as e:
                logger.warning(f"   ⚠️ No se pudo registrar en caja: {e}")
                result['warnings'].append(f"No se pudo registrar en caja: {e}")
            except Exception as e:
                logger.error(f"   ❌ Error al registrar en caja: {e}")
                result['errors'].append(f"Error al registrar en caja: {e}")
        
        # ============================================================
        # 5. CREAR PAGO (si no existe)
        # ============================================================
        payment_exists = Payment.objects.filter(
            sale_invoice=invoice,
            status='COMPLETED'
        ).exists()
        
        if not payment_exists:
            try:
                default_method = PaymentMethod.objects.filter(
                    company=invoice.company,
                    is_active=True
                ).first()
                
                if default_method:
                    try:
                        usd = Currency.objects.get(code='USD')
                    except Currency.DoesNotExist:
                        usd = None
                    
                    if usd:
                        Payment.objects.create(
                            sale_invoice=invoice,
                            method=default_method,
                            currency=usd,
                            amount=invoice.total,
                            amount_usd=invoice.total,
                            reference=f"Pago factura {invoice.number}",
                            status='COMPLETED',
                            user=user,
                            company=invoice.company,
                        )
                        result['payment_created'] = True
                        logger.info(f"   ✅ Pago creado")
            except Exception as e:
                logger.error(f"   ❌ Error creando pago: {e}")
                result['errors'].append(f"Error creando pago: {e}")
        else:
            logger.info(f"   ℹ️ Pago ya existe para {invoice.number}")
        
        # ============================================================
        # 6. REDUCIR INVENTARIO (con verificación de duplicados)
        # ============================================================
        if not skip_inventory:
            already_reduced = Movement.objects.filter(
                source_reference=invoice.number,
                source_type='SALE'
            ).exists()
            
            if already_reduced:
                logger.info(f"   ℹ️ Inventario ya reducido para {invoice.number}")
            elif not invoice.lines.exists():
                msg = "La factura no tiene líneas, no se reduce inventario"
                logger.warning(f"   ⚠️ {msg}")
                result['warnings'].append(msg)
            else:
                try:
                    movements = SaleInvoiceProcessingService._reduce_inventory(
                        invoice, user, company
                    )
                    result['inventory_reduced'] = True
                    result['movements_created'] = len(movements)
                    logger.info(f"   ✅ {len(movements)} movimientos creados")
                except Exception as e:
                    logger.error(f"   ❌ Error al reducir inventario: {e}")
                    result['errors'].append(f"Error al reducir inventario: {e}")
                    raise  # Propagar para que la transacción se revierta
        
        # ============================================================
        # 7. ENVIAR SEÑAL invoice_paid
        # ============================================================
        try:
            from .signals import invoice_paid
            invoice_paid.send(sender=SaleInvoice, invoice=invoice, request=request)
            logger.info(f"   📨 Señal invoice_paid enviada")
        except Exception as e:
            logger.warning(f"   ⚠️ Error enviando señal invoice_paid: {e}")
        
        logger.info("=" * 80)
        return result
    
    @staticmethod
    def _reduce_inventory(invoice, user, company):
        """
        Reduce el inventario para cada línea de la factura.
        ✅ REFACTORIZADO: usa WarehouseService.create_exit() para unificar
        la lógica de salida de inventario en un solo lugar.
        """
        from django_erp.inventory.models import Inventory, Location
        from django_erp.inventory.services import WarehouseService, InventoryService
        
        logger.info("   🔴 [_reduce_inventory] INICIANDO")
        
        if not invoice.lines.exists():
            logger.warning("   ⚠️ La factura no tiene líneas")
            return []
        
        movements_created = []
        
        for idx, line in enumerate(invoice.lines.all(), 1):
            logger.info(f"   📝 Procesando línea {idx}: {line.product_name}")
            
            if not line.product:
                logger.warning(f"      ⚠️ Línea sin producto, saltando...")
                continue
            
            if line.product.is_service:
                logger.info(f"      ℹ️ {line.product.name} es un servicio, no se reduce inventario")
                continue
            
            # ✅ Buscar ubicación con stock (lógica del servicio de inventario)
            location = InventoryService.find_location_with_stock(
                product=line.product,
                company=company,
                required_quantity=line.quantity
            )
            
            if not location:
                # Fallback: usar la primera ubicación activa
                location = Location.objects.filter(
                    company=company,
                    is_active=True
                ).first()
            
            if not location:
                raise ValidationError(
                    f"No hay ubicación para el producto {line.product.name}. "
                    f"Configura una ubicación en Inventario > Ubicaciones."
                )
            
            # ✅ Verificar stock
            stock = InventoryService.get_stock_by_location(
                line.product.id, location.id, company
            )
            
            if stock < line.quantity:
                raise ValidationError(
                    f"Stock insuficiente para '{line.product.name}'. "
                    f"Disponible: {stock}, Requerido: {line.quantity}"
                )
            
            # ✅ Delegar la creación del movimiento a WarehouseService
            #    (así queda un único punto de entrada para salidas)
            movement = WarehouseService.create_exit(
                product_id=line.product.id,
                quantity=line.quantity,
                location_from_id=location.id,
                unit_price=line.unit_price,
                source_type='SALE',
                source_reference=invoice.number,
                note=f"Factura {invoice.number} - {invoice.customer_name or 'Sin cliente'}",
                user=user,
                company=company
            )
            movements_created.append(movement)
            logger.info(f"      ✅ Movimiento {movement.id} creado")
        
        return movements_created