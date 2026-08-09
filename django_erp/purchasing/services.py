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
        """Confirmar orden por parte del proveedor (ENVIADO → CONFIRMADO)"""
        logger.info(f"✅ Confirmando orden {order.number} por proveedor")
        
        if order.status != 'SENT':
            raise ValidationError(
                f"No se puede confirmar una orden que no ha sido enviada. "
                f"Estado actual: {order.get_status_display()}"
            )
        
        order.status = 'CONFIRMED'
        order.confirmed_date = timezone.now()
        order.save()
        
        logger.info(f"✅ Orden {order.number} confirmada por proveedor")
        return order
    
    @staticmethod
    @transaction.atomic
    def receive_order(order, user=None):
        """
        Recibir orden de compra (CONFIRMADO → RECIBIDO)
        Crea movimientos de entrada en el inventario
        """
        logger.info(f"📦 Recibiendo orden {order.number}")
        
        if order.status != 'CONFIRMED':
            raise ValidationError(
                f"No se puede recibir una orden que no está confirmada. "
                f"Estado actual: {order.get_status_display()}"
            )
        
        if not order.lines.exists():
            raise ValidationError("No se puede recibir una orden sin líneas")
        
        company = order.company
        if not company:
            raise ValidationError("No hay una compañía asociada a esta orden.")
        
        # Crear Nota de Recibo en el módulo de inventario
        from django_erp.inventory.models import ReceiptNote, ReceiptNoteLine, Location
        
        # Crear la nota de recibo
        receipt_note = ReceiptNote.objects.create(
            supplier=order.supplier,
            supplier_name=order.supplier.name,
            notes=f"Recepción automática de orden {order.number}",
            status='DRAFT',
            user=user or order.user,
            company=company,
        )
        
        # Crear líneas de la nota de recibo
        for line in order.lines.all():
            if not line.product:
                logger.warning(f"⚠️ Línea {line.id} sin producto, saltando...")
                continue
            
            if line.product.is_service:
                logger.info(f"ℹ️ Producto {line.product.name} es servicio, no se recibe en inventario")
                continue
            
            # Buscar ubicación sugerida o usar la primera disponible
            location = line.location
            if not location:
                # Buscar una ubicación por defecto para esta compañía
                location = Location.objects.filter(
                    company=company,
                    is_active=True
                ).first()
                
                if not location:
                    # Crear ubicación por defecto
                    location = Location.objects.create(
                        code=f"ALM-{company.code}",
                        name=f"Almacén Principal - {company.name}",
                        description=f"Almacén principal de {company.name}",
                        company=company,
                        is_active=True
                    )
                    logger.info(f"✅ Creada ubicación por defecto: {location.code}")
            
            if not location:
                raise ValidationError(
                    f"No hay ubicación para el producto {line.product.name} en {company.code}"
                )
            
            # Crear línea en la nota de recibo
            ReceiptNoteLine.objects.create(
                note=receipt_note,
                product=line.product,
                location=location,
                quantity=line.quantity,
                company=company,
            )
        
        # Confirmar la nota de recibo (esto crea los movimientos de inventario)
        from django_erp.inventory.services import InventoryService
        InventoryService.confirm_receipt_note(receipt_note.id, user)
        
        # Actualizar la orden de compra
        order.status = 'RECEIVED'
        order.received_date = timezone.now()
        order.save()
        
        logger.info(f"✅ Orden {order.number} recibida exitosamente")
        logger.info(f"✅ Nota de recibo {receipt_note.number} creada y confirmada")
        
        # Generar factura automáticamente
        try:
            invoice = PurchaseInvoiceService.create_invoice_from_purchase_order(
                order.id, 
                user or order.user
            )
            logger.info(f"✅ Factura {invoice.number} generada automáticamente")
        except Exception as e:
            logger.error(f"❌ Error generando factura: {e}")
            # No detener el proceso si falla la factura
        
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
    def can_transition(order, new_status):
        """Verificar si una transición de estado es válida"""
        valid_transitions = {
            'DRAFT': ['SENT', 'CANCELLED'],
            'SENT': ['CONFIRMED', 'CANCELLED'],
            'CONFIRMED': ['RECEIVED', 'CANCELLED'],
            'RECEIVED': [],  # No se puede cambiar desde RECIBIDO
            'CANCELLED': [],  # No se puede cambiar desde CANCELADO
        }
        
        return new_status in valid_transitions.get(order.status, [])


class PurchaseInvoiceService:
    """Servicio para facturas de compra"""
    
    @staticmethod
    @transaction.atomic
    def create_invoice_from_purchase_order(purchase_order_id, user=None):
        """
        Crear factura de compra desde una orden de compra recibida
        """
        from datetime import datetime, timedelta
        
        purchase_order = PurchaseOrder.objects.get(id=purchase_order_id)
        
        # ✅ Validaciones
        if purchase_order.status != 'RECEIVED':
            raise ValidationError("Solo se pueden facturar órdenes recibidas")
        
        if purchase_order.invoiced:
            raise ValidationError("Esta orden ya tiene una factura")
        
        # ✅ Obtener empresa (usar la de la orden)
        company = purchase_order.company
        if not company:
            raise ValidationError("No hay una empresa configurada para esta orden")
        
        # ✅ Generar número de factura
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
        
        # ✅ Crear factura
        invoice = PurchaseInvoice.objects.create(
            number=number,
            purchase_order=purchase_order,
            supplier=purchase_order.supplier,
            supplier_name=purchase_order.supplier.name,
            supplier_rif=purchase_order.supplier.tax_id,
            supplier_address=purchase_order.supplier.address,
            date_due=datetime.now().date() + timedelta(days=30),
            status='DRAFT',
            user=user or purchase_order.user,
            sync_status='SYNCED',
            company=company,
        )
        
        # ✅ Copiar líneas CON COMPAÑÍA
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
        
        # ✅ Calcular totales
        invoice.calculate_totals()
        invoice.save()
        
        # ✅ Actualizar orden
        purchase_order.invoice_ids.add(invoice)
        purchase_order.invoiced = True
        purchase_order.invoice_date = datetime.now().date()
        purchase_order.save()
        
        logger.info(f'✅ Factura de compra {invoice.number} creada desde orden {purchase_order.number}')
        logger.info(f'   Compañía: {company.code} - {company.name}')
        
        return invoice


class PurchaseOrderService:
    """Servicio adicional para consultas de órdenes de compra"""
    
    @staticmethod
    def get_order_status_summary(company=None):
        """
        Obtener resumen de estados de órdenes de compra
        """
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
        """
        Obtener órdenes filtradas por estado
        """
        queryset = PurchaseOrder.objects.filter(status=status)
        if company:
            queryset = queryset.filter(company=company)
        return queryset.order_by('-created_at')