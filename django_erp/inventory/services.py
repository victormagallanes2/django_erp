# inventory/services.py
from django.db import transaction
from django.core.exceptions import ValidationError
from .models import Inventory, ValuationMethod, PhysicalCount

# ✅ Importamos servicios, NO modelos
# ✅ Usamos get_model para resolver referencias dinámicas
from django.apps import apps


class InventoryService:
    """Servicios de gestión contable de inventario"""
    
    @staticmethod
    def _get_product_model():
        """Obtener modelo Product de forma dinámica"""
        return apps.get_model('warehouse', 'Product')
    
    @staticmethod
    def _get_location_model():
        """Obtener modelo Location de forma dinámica"""
        return apps.get_model('warehouse', 'Location')
    
    @staticmethod
    def get_stock_by_location(product_id, location_id):
        """Obtener stock de un producto en una ubicación específica"""
        try:
            inventory = Inventory.objects.get(product_id=product_id, location_id=location_id)
            return inventory.quantity
        except Inventory.DoesNotExist:
            return 0
    
    @staticmethod
    def get_total_stock(product_id):
        """Obtener stock total de un producto en todas las ubicaciones"""
        inventories = Inventory.objects.filter(product_id=product_id)
        return sum(inv.quantity for inv in inventories) if inventories else 0
    
    @staticmethod
    @transaction.atomic
    def update_stock_from_movement(movement):
        """Actualizar inventario desde un movimiento físico"""
        # movement viene de warehouse.models.Movement (referencia dinámica)
        # pero es un objeto real, podemos usarlo directamente
        
        inventory, created = Inventory.objects.get_or_create(
            product=movement.product,
            location=movement.location_to or movement.location_from,
        )
        
        if movement.type == 'ENTRY':
            inventory.quantity += movement.quantity
            # Actualizar costo promedio (si tiene unit_price)
            if hasattr(movement, 'unit_price') and movement.unit_price:
                inventory.average_cost = (
                    (inventory.average_cost * (inventory.quantity - movement.quantity) +
                     movement.unit_price * movement.quantity) / inventory.quantity
                )
        elif movement.type == 'EXIT':
            if inventory.quantity < movement.quantity:
                raise ValidationError("Stock insuficiente")
            inventory.quantity -= movement.quantity
        
        inventory.total_value = inventory.quantity * inventory.average_cost
        inventory.save()
    
    @staticmethod
    @transaction.atomic
    def confirm_physical_count(count_id):
        """Confirmar un conteo físico y ajustar stock"""
        count = PhysicalCount.objects.get(id=count_id)
        
        if count.status != 'DRAFT':
            raise ValidationError("Solo se pueden confirmar conteos en borrador")
        
        # Actualizar inventario con el conteo
        inventory, created = Inventory.objects.get_or_create(
            product=count.product,
            location=count.location,
        )
        inventory.quantity = count.counted_quantity
        inventory.save()
        
        count.status = 'CONFIRMED'
        count.save()
        
        return count