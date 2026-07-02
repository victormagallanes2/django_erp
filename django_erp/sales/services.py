# sales/services.py
from django.db import transaction
from django.core.exceptions import ValidationError
from .models import Customer, SaleOrder, SaleLine
from django_erp.warehouse.services import WarehouseService
from django_erp.inventory.services import InventoryService


class SaleService:
    """Servicios de ventas"""
    
    @staticmethod
    @transaction.atomic
    def create_order(customer_id, items, note='', user=None):
        customer = Customer.objects.get(id=customer_id)
        
        import datetime
        last_order = SaleOrder.objects.order_by('-id').first()
        if last_order and last_order.number:
            try:
                last_num = int(last_order.number.split('-')[-1])
                next_num = last_num + 1
            except (ValueError, IndexError):
                next_num = 1
        else:
            next_num = 1
        
        number = f"VENTA-{datetime.datetime.now().strftime('%Y%m%d')}-{next_num:04d}"
        
        order = SaleOrder.objects.create(
            number=number,
            customer=customer,
            status='DRAFT',
            note=note,
            user=user
        )
        
        for item in items:
            SaleLine.objects.create(
                order=order,
                product_id=item['product_id'],
                location_id=item.get('location_id'),
                quantity=item['quantity'],
                unit_price=item['unit_price']
            )
        
        order.calculate_totals()
        order.save()
        
        return order
    
    @staticmethod
    @transaction.atomic
    def confirm_order(order, user=None):
        """Confirmar una orden"""
        
        for line in order.lines.all():
            stock = InventoryService.get_stock_by_location(line.product_id, line.location_id)
            if stock < line.quantity:
                raise ValidationError(
                    f"Stock insuficiente para {line.product.name} en {line.location.code}"
                )
            
            WarehouseService.create_exit(
                product_id=line.product_id,
                quantity=line.quantity,
                location_from_id=line.location_id,
                source_type='SALE',
                source_reference=order.number,
                note=f"Venta {order.number} - {order.customer.name}",
                user=user
            )
        
        return order

    @staticmethod
    @transaction.atomic
    def cancel_order(order, user=None, old_status=None):
        """Cancelar una orden y devolver stock"""
        
        # ✅ Usar el estado anterior para saber si había stock que devolver
        status_before_cancel = old_status or order.status
        
        # Si estaba confirmada, devolver stock
        if status_before_cancel == 'CONFIRMED':
            for line in order.lines.all():
                WarehouseService.create_entry(
                    product_id=line.product.id,
                    quantity=line.quantity,
                    location_to_id=line.location.id,
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
        return order