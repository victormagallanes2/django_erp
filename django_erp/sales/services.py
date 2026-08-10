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
        
        # ============================================================
        # 💰 3. REGISTRAR EN CAJA (solo si hay total > 0)
        # ============================================================
        
        if order.total > 0:
            from .models import CashTransaction
            from .helpers import get_open_register
            
            try:
                register = get_open_register(user or order.user)
                
                CashTransaction.objects.create(
                    register=register,
                    type='SALE',
                    amount=order.total,
                    description=f"Venta {order.number} - {order.customer.name}",
                    reference=order.number,
                    user=user or order.user,
                    company=company,
                )
                
                register.calculate_totals()
                logger.info(f"   ✅ Transacción registrada en caja {register.number}")
                
            except ValidationError as e:
                logger.warning(f"   ⚠️ Error al registrar en caja: {e}")
        
        logger.info("=" * 80)
        return order
    
    @staticmethod
    @transaction.atomic
    def deliver_order(order, user=None):
        """
        ✅ Entregar una orden (llamado desde la confirmación de la nota de entrega).
        - Marca la orden como DELIVERED
        - Genera la factura de venta
        """
        from .models import SaleInvoice, SaleInvoiceLine
        
        logger.info("=" * 80)
        logger.info(f"🔴 [deliver_order] Entregando orden {order.number}")
        
        if order.status != 'CONFIRMED':
            logger.warning(f"   ⚠️ La orden no está confirmada (estado: {order.status})")
            raise ValidationError("Solo se pueden entregar órdenes confirmadas.")
        
        if order.status == 'DELIVERED':
            logger.info(f"   ℹ️ La orden ya estaba entregada")
            return order
        
        # ✅ Marcar como entregada
        order.status = 'DELIVERED'
        order.delivered_date = timezone.now()
        order.save()
        logger.info(f"   ✅ Orden {order.number} marcada como DELIVERED")
        
        # ============================================================
        # 📄 GENERAR FACTURA DE VENTA
        # ============================================================
        
        try:
            # ✅ Verificar si ya existe factura para esta orden
            existing_invoice = SaleInvoice.objects.filter(
                sale_order=order,
                company=order.company
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
            
            # ✅ Obtener tasa de IVA de la empresa
            company = order.company or Company.get_active()
            tax_rate = Decimal(str(company.tax_rate)) if company else Decimal('16.00')
            
            # ✅ Crear la factura
            invoice = SaleInvoice.objects.create(
                number=number,
                sale_order=order,
                customer=order.customer,
                customer_name=order.customer.name,
                customer_tax_id=order.customer.tax_id,
                customer_address=order.customer.address,
                date_due=datetime.now().date() + timedelta(days=30),
                status='ISSUED',  # Emitida automáticamente
                tax_rate=tax_rate,
                user=user or order.user,
                sync_status='SYNCED',
                company=order.company,
            )
            logger.info(f"   ✅ Factura creada: {invoice.number}")
            
            # ✅ Copiar líneas de la orden a la factura
            lines_count = 0
            for sale_line in order.lines.all():
                SaleInvoiceLine.objects.create(
                    invoice=invoice,
                    sale_line=sale_line,
                    product=sale_line.product,
                    product_code=sale_line.product_code if sale_line.product else '',
                    product_name=sale_line.product_name or (sale_line.product.name if sale_line.product else ''),
                    description=sale_line.description,
                    quantity=sale_line.quantity,
                    unit_price=sale_line.unit_price,
                    subtotal=sale_line.subtotal,
                    company=order.company,
                )
                lines_count += 1
            
            logger.info(f"   ✅ {lines_count} líneas copiadas a la factura")
            
            # ✅ Calcular totales
            invoice.calculate_totals()
            invoice.save()
            logger.info(f"   ✅ Totales calculados: Subtotal={invoice.subtotal}, IVA={invoice.tax}, Total={invoice.total}")
            
            # ✅ Agregar factura a la orden
            order.invoices.add(invoice)  # Si el campo existe, o simplemente referenciar
            
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
        
        tax_rate = Decimal(str(company.tax_rate)) if company else Decimal('16.00')
        
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
        queryset = SaleOrder.objects.filter(status__in=['CONFIRMED', 'DELIVERED'])

        if company:
            queryset = queryset.filter(company=company)
        else:
            company = Company.get_active()
            if company:
                queryset = queryset.filter(company=company)

        if period_type == 'day':
            start_date = timezone.now() - timedelta(days=days_back)
            queryset = queryset.filter(date__gte=start_date)
            trunc_function = TruncDay('date')
            label_format = '%d-%m'
        elif period_type == 'month':
            start_date = timezone.now() - timedelta(days=365)
            queryset = queryset.filter(date__gte=start_date)
            trunc_function = TruncMonth('date')
            label_format = 'b Y'
        elif period_type == 'year':
            start_date = timezone.now() - timedelta(days=3650)
            queryset = queryset.filter(date__gte=start_date)
            trunc_function = TruncYear('date')
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

        queryset = SaleOrder.objects.filter(status__in=['CONFIRMED', 'DELIVERED'])

        if company:
            queryset = queryset.filter(company=company)
        else:
            company = Company.get_active()
            if company:
                queryset = queryset.filter(company=company)

        sales_today = queryset.filter(date=today).aggregate(Sum('total'))['total__sum'] or Decimal('0.00')
        sales_this_month = queryset.filter(date__gte=first_day_of_month).aggregate(Sum('total'))['total__sum'] or Decimal('0.00')
        sales_this_year = queryset.filter(date__gte=first_day_of_year).aggregate(Sum('total'))['total__sum'] or Decimal('0.00')

        return {
            'today': float(sales_today),
            'this_month': float(sales_this_month),
            'this_year': float(sales_this_year),
        }