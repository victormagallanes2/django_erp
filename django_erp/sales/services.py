# sales/services.py
from django.db import transaction
from django.core.exceptions import ValidationError
from django.apps import apps
from .models import SaleOrder


class SaleService:
    """Servicios de ventas - Soporta productos y servicios"""
    
    @staticmethod
    @transaction.atomic
    def confirm_order(order, user=None):
        """✅ Confirmar una orden - Productos físicos y servicios"""
        
        # ============================================================
        # 📦 1. PROCESAR PRODUCTOS Y SERVICIOS
        # ============================================================
        
        for line in order.lines.all():
            if line.product:
                # ✅ Si es servicio, no verificar stock
                if line.product.is_service:
                    print(f"📝 Servicio confirmado: {line.product.name}")
                    continue
                
                # ✅ Si es producto físico, verificar stock
                if apps.is_installed('django_erp.inventory'):
                    from django_erp.inventory.services import InventoryService
                    stock = InventoryService.get_stock_by_location(
                        line.product.id,
                        line.location.id if line.location else None
                    )
                    if stock < line.quantity:
                        raise ValidationError(
                            f"❌ Stock insuficiente para {line.product.name}. "
                            f"Disponible: {stock}, Solicitado: {line.quantity}"
                        )
                
                # ✅ Crear movimiento de salida para productos físicos
                if apps.is_installed('django_erp.warehouse'):
                    from django_erp.warehouse.services import WarehouseService
                    WarehouseService.create_exit(
                        product_id=line.product.id,
                        quantity=line.quantity,
                        location_from_id=line.location.id if line.location else None,
                        unit_price=line.unit_price,
                        source_type='SALE',
                        source_reference=order.number,
                        note=f"Venta {order.number} - {order.customer.name}",
                        user=user or order.user
                    )
                else:
                    print(f"ℹ️ Warehouse no instalado. No se reduce stock para {line.product.name}")
            else:
                print(f"📝 Servicio confirmado: {line.product_name or line.description or 'Servicio'}")
        
        # ============================================================
        # ✅ 2. ACTUALIZAR ESTADO DE LA ORDEN
        # ============================================================
        
        order.status = 'CONFIRMED'
        order.save()
        
        # ============================================================
        # 💰 3. REGISTRAR EN CAJA
        # ============================================================
        
        if apps.is_installed('django_erp.sales'):
            from .models import CashTransaction
            from .helpers import get_open_register
            
            try:
                # 🔍 Obtener la caja abierta del usuario
                register = get_open_register(user or order.user)
                
                # 📝 Crear transacción de caja
                CashTransaction.objects.create(
                    register=register,
                    type='SALE',
                    amount=order.total,
                    description=f"Venta {order.number} - {order.customer.name}",
                    reference=order.number,
                    user=user or order.user
                )
                
                # 🔄 Recalcular totales de la caja
                register.calculate_totals()
                
                print(f"✅ Transacción registrada en caja {register.number}")
                
            except ValidationError as e:
                print(f"⚠️ Error al registrar en caja: {e}")
                # ⚠️ Lanzar error para que la transacción se revierta
                raise ValidationError(f"❌ Error al registrar en caja: {str(e)}")
        
        # ============================================================
        # 📄 4. GENERAR FACTURA (SI ESTÁ INSTALADO INVOICING)
        # ============================================================
        
        if apps.is_installed('django_erp.invoicing'):
            try:
                from django_erp.invoicing.services import InvoiceService
                InvoiceService.create_invoice_from_sale_order(order.id, user or order.user)
                print(f"✅ Factura generada para orden {order.number}")
            except Exception as e:
                print(f"⚠️ Error al generar factura: {e}")
                # No detener el proceso si falla la factura
                # raise ValidationError(f"Error al generar factura: {str(e)}")
        
        return order
    
    @staticmethod
    @transaction.atomic
    def cancel_order(order, user=None, old_status=None):
        """Cancelar una orden"""
        
        if order.status in ['DELIVERED', 'CANCELLED']:
            raise ValidationError("No se puede cancelar una orden entregada o ya cancelada")
        
        if old_status == 'CONFIRMED':
            for line in order.lines.all():
                # ✅ Solo devolver stock si es producto físico
                if line.product and not line.product.is_service:
                    if apps.is_installed('django_erp.warehouse'):
                        from django_erp.warehouse.services import WarehouseService
                        WarehouseService.create_entry(
                            product_id=line.product.id,
                            quantity=line.quantity,
                            location_to_id=line.location.id if line.location else None,
                            source_type='MANUAL',
                            source_reference=f"CANCEL-{order.number}",
                            note=f"Cancelación de venta {order.number}",
                            user=user or order.user
                        )
        
        return order
    
    @staticmethod
    @transaction.atomic
    def deliver_order(order, user=None):
        """Entregar una orden"""
        if order.status != 'CONFIRMED':
            raise ValidationError("Solo se pueden entregar órdenes confirmadas")
        return order