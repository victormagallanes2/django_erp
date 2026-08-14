# django_erp/purchasing/services.py
from django.db import transaction
from django.core.exceptions import ValidationError
from django.apps import apps
from django.utils import timezone
from .models import PurchaseOrder, PurchaseInvoice, PurchaseInvoiceLine
from decimal import Decimal
import logging
import traceback
from django_erp.configuration.models import Company, ExchangeRate

logger = logging.getLogger(__name__)


class PurchaseService:
    """Servicios de compras - Flujo completo"""
    
    @staticmethod
    @transaction.atomic
    def send_order(order, user=None):
        """Enviar orden al proveedor (BORRADOR → ENVIADO)"""
        logger.info(f"📤 Enviando orden {order.number} al proveedor")
        
        if order.status != 'DRAFT':
            raise ValidationError(
                f"No se puede enviar una orden en estado '{order.get_status_display()}'."
            )
        
        if not order.lines.exists():
            raise ValidationError("No se puede enviar una orden sin líneas.")
        
        order.status = 'SENT'
        order.sent_date = timezone.now()
        order.save()
        
        logger.info(f"✅ Orden {order.number} enviada al proveedor")
        return order
    
    @staticmethod
    @transaction.atomic
    def confirm_order_from_supplier(order, user=None):
        """Confirmar orden por parte del proveedor (ENVIADO → CONFIRMADO)."""
        logger.info("=" * 80)
        logger.info(f"🔴 [confirm_order_from_supplier] Confirmando orden {order.number}")
        
        if order.status != 'SENT':
            raise ValidationError(
                f"No se puede confirmar una orden que no ha sido enviada. "
                f"Estado actual: {order.get_status_display()}"
            )
        
        order.status = 'CONFIRMED'
        order.confirmed_date = timezone.now()
        order.save()
        
        logger.info(f"✅ Orden {order.number} confirmada por proveedor")

        try:
            logger.info("   📝 Creando nota de recibo en borrador...")
            receipt_note = PurchaseService._create_draft_receipt_note(order, user)
            if receipt_note:
                logger.info(f"   ✅ Nota de recibo {receipt_note.number} creada en Borrador")
            else:
                logger.warning("   ⚠️ No se pudo crear la nota de recibo")
        except Exception as e:
            logger.error(f"   ❌ Error creando nota de recibo: {e}")
        
        logger.info("=" * 80)
        return order

    @staticmethod
    def _create_draft_receipt_note(order, user=None):
        """Crear una Nota de Recibo en Borrador para la orden."""
        from django_erp.inventory.models import ReceiptNote, ReceiptNoteLine, Location

        logger.info("=" * 80)
        logger.info("🔴 [_create_draft_receipt_note] CREANDO NOTA DE RECIBO")
        logger.info(f"   Orden: {order.number}")

        existing = order.receipt_notes.filter(status__in=['DRAFT', 'CONFIRMED']).order_by('-id').first()
        if existing:
            logger.info(f"   ℹ️ Ya existe una nota {existing.number} en estado {existing.status}")
            logger.info("=" * 80)
            return existing

        if not order.lines.exists():
            logger.warning(f"   ⚠️ Orden {order.number} sin líneas")
            logger.info("=" * 80)
            return None

        company = order.company
        if not company:
            logger.error("   ❌ No hay compañía asociada a la orden")
            raise ValidationError("No hay una compañía asociada a esta orden.")
        
        logger.info(f"   Compañía: {company.code} - {company.name}")

        receipt_note = ReceiptNote.objects.create(
            purchase_order=order,
            supplier=order.supplier,
            supplier_name=order.supplier.name,
            notes=f"Recepción de orden {order.number}",
            status='DRAFT',
            user=user or order.user,
            company=company,
        )
        logger.info(f"   ✅ Nota de recibo creada: {receipt_note.number}")

        lines_created = 0
        for line in order.lines.all():
            if not line.product:
                logger.warning(f"   ⚠️ Línea {line.id} sin producto, saltando...")
                continue

            if line.product.is_service:
                logger.info(f"   ℹ️ Producto {line.product.name} es servicio, no se recibe en inventario")
                continue

            location = line.location
            if not location:
                logger.info(f"   🔍 Buscando ubicación por defecto...")
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
                    logger.info(f"   ✅ Creada ubicación por defecto: {location.code}")

            if not location:
                logger.error(f"   ❌ No hay ubicación para el producto {line.product.name}")
                raise ValidationError(
                    f"No hay ubicación para el producto {line.product.name} en {company.code}"
                )

            ReceiptNoteLine.objects.create(
                note=receipt_note,
                product=line.product,
                location=location,
                quantity=line.quantity,
                company=company,
            )
            lines_created += 1
            logger.info(f"   ✅ Línea {lines_created}: {line.product.name} x {line.quantity} en {location.code}")

        logger.info(f"   📊 Total líneas creadas: {lines_created}")
        logger.info("=" * 80)
        return receipt_note
    
    @staticmethod
    @transaction.atomic
    def receive_order(order, user=None):
        """Recibir orden de compra (CONFIRMADO → RECIBIDO)."""
        logger.info(f"📦 Recibiendo orden {order.number}")

        if order.status == 'RECEIVED':
            logger.info(f"ℹ️ La orden {order.number} ya está recibida")
            return order
        
        if order.status != 'CONFIRMED':
            raise ValidationError(
                f"No se puede recibir una orden que no está confirmada. "
                f"Estado actual: {order.get_status_display()}"
            )
        
        if not order.lines.exists():
            raise ValidationError("No se puede recibir una orden sin líneas")

        from django_erp.inventory.services import InventoryService

        receipt_note = order.receipt_notes.filter(status='DRAFT').order_by('-id').first()
        if not receipt_note:
            receipt_note = PurchaseService._create_draft_receipt_note(order, user)

        if not receipt_note:
            raise ValidationError("No se pudo crear/obtener la nota de recibo para esta orden.")

        InventoryService.confirm_receipt_note(receipt_note.id, user)

        order.refresh_from_db()
        logger.info(f"✅ Orden {order.number} recibida exitosamente")
        return order

    @staticmethod
    @transaction.atomic
    def finalize_receipt(order, user=None):
        """
        Marca la orden como RECIBIDA y genera su factura de compra.
        """
        logger.info("=" * 80)
        logger.info("🔴 [finalize_receipt] INICIANDO")
        logger.info(f"   Orden: {order.number}")
        logger.info(f"   Estado actual: {order.status}")
        logger.info(f"   ¿Ya facturada?: {order.invoiced}")

        if order.status == 'RECEIVED':
            logger.info(f"   ℹ️ La orden ya estaba marcada como recibida")
            logger.info("=" * 80)
            return order

        order.status = 'RECEIVED'
        order.received_date = timezone.now()
        order.save()
        logger.info(f"   ✅ Orden marcada como RECIBIDA")

        # ✅ Generar factura solo si no tiene factura
        if not order.invoiced:
            logger.info("   📄 Generando factura de compra...")
            try:
                from .services import PurchaseInvoiceService
                invoice = PurchaseInvoiceService.create_invoice_from_purchase_order(
                    order.id,
                    user or order.user
                )
                logger.info(f"   ✅ Factura {invoice.number} generada automáticamente")
            except Exception as e:
                logger.error(f"   ❌ Error generando factura: {e}")
                logger.error(f"   Traceback: {traceback.format_exc()}")
        else:
            logger.info(f"   ⚠️ La orden ya tiene factura, no se genera otra")

        logger.info("🔴 [finalize_receipt] FINALIZADO")
        logger.info("=" * 80)
        return order
    
    @staticmethod
    @transaction.atomic
    def cancel_order(order, user=None):
        """Cancelar orden en cualquier estado (excepto RECEIVED)"""
        logger.info(f"❌ Cancelando orden {order.number}")
        
        if order.status == 'RECEIVED':
            raise ValidationError("No se puede cancelar una orden ya recibida")
        
        if order.status == 'CANCELLED':
            logger.info("ℹ️ La orden ya está cancelada")
            return order
        
        order.status = 'CANCELLED'
        order.save()
        
        logger.info(f"✅ Orden {order.number} cancelada")
        return order
    
    @staticmethod
    def can_transition(order, new_status, current_status=None):
        """Verificar si una transición de estado es válida."""
        valid_transitions = {
            'DRAFT': ['SENT', 'CANCELLED'],
            'SENT': ['CONFIRMED', 'CANCELLED'],
            'CONFIRMED': ['RECEIVED', 'CANCELLED'],
            'RECEIVED': [],
            'CANCELLED': [],
        }

        status = current_status if current_status is not None else order.status
        return new_status in valid_transitions.get(status, [])


class PurchaseInvoiceService:
    """Servicio para facturas de compra"""
    
    @staticmethod
    @transaction.atomic
    def create_invoice_from_purchase_order(purchase_order_id, user=None):
        """Crear factura de compra desde una orden de compra recibida"""
        from datetime import datetime, timedelta
        
        logger.info("=" * 80)
        logger.info("🔴 [create_invoice_from_purchase_order] CREANDO FACTURA")
        logger.info(f"   purchase_order_id: {purchase_order_id}")
        
        try:
            purchase_order = PurchaseOrder.objects.get(id=purchase_order_id)
            logger.info(f"   ✅ Orden encontrada: {purchase_order.number}")
            logger.info(f"   Estado: {purchase_order.status}")
            logger.info(f"   ¿Ya facturada?: {purchase_order.invoiced}")
        except PurchaseOrder.DoesNotExist as e:
            logger.error(f"   ❌ Orden no encontrada: {e}")
            raise
        
        if purchase_order.status != 'RECEIVED':
            logger.error(f"   ❌ La orden no está recibida (estado: {purchase_order.status})")
            raise ValidationError("Solo se pueden facturar órdenes recibidas")
        
        if purchase_order.invoiced:
            logger.warning(f"   ⚠️ Esta orden ya tiene una factura")
            raise ValidationError("Esta orden ya tiene una factura")
        
        company = purchase_order.company
        if not company:
            logger.error("   ❌ No hay una empresa configurada para esta orden")
            raise ValidationError("No hay una empresa configurada para esta orden")
        
        logger.info(f"   Compañía: {company.code} - {company.name}")
        
        last_invoice = PurchaseInvoice.objects.order_by('-id').first()
        if last_invoice and last_invoice.number:
            try:
                last_num = int(last_invoice.number.split('-')[-1])
                next_num = last_num + 1
            except (ValueError, IndexError):
                next_num = 1
        else:
            next_num = 1
        
        number = f"FAC-COMPRA-{datetime.now().strftime('%Y%m')}-{next_num:04d}"
        logger.info(f"   Número de factura generado: {number}")
        
        invoice = PurchaseInvoice.objects.create(
            number=number,
            purchase_order=purchase_order,
            supplier=purchase_order.supplier,
            supplier_name=purchase_order.supplier.name,
            supplier_rif=purchase_order.supplier.tax_id,
            supplier_address=purchase_order.supplier.address,
            date_due=datetime.now().date() + timedelta(days=30),
            status='PAID',
            user=user or purchase_order.user,
            sync_status='SYNCED',
            company=company,
        )
        logger.info(f"   ✅ Factura creada: {invoice.number}")
        
        lines_count = 0
        for line in purchase_order.lines.all():
            PurchaseInvoiceLine.objects.create(
                invoice=invoice,
                purchase_line=line,
                product=line.product,
                product_code=line.product_code,
                product_name=line.product_name,
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
        
        purchase_order.invoice_ids.add(invoice)
        purchase_order.invoiced = True
        purchase_order.invoice_date = datetime.now().date()
        purchase_order.save()
        logger.info(f"   ✅ Orden {purchase_order.number} marcada como facturada")
        
        logger.info(f"✅ Factura de compra {invoice.number} creada")
        logger.info("=" * 80)
        return invoice


class PurchaseOrderService:
    """Servicio adicional para consultas de órdenes de compra"""
    
    @staticmethod
    def get_order_status_summary(company=None):
        from django.db.models import Count
        queryset = PurchaseOrder.objects.all()
        if company:
            queryset = queryset.filter(company=company)
        summary = queryset.values('status').annotate(
            count=Count('id')
        ).order_by('status')
        return summary
    
    @staticmethod
    def get_orders_by_status(status, company=None):
        queryset = PurchaseOrder.objects.filter(status=status)
        if company:
            queryset = queryset.filter(company=company)
        return queryset.order_by('-created_at')