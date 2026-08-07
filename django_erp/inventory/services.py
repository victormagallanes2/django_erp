# inventory/services.py
from django.db import transaction
from django.core.exceptions import ValidationError
from .models import Inventory, ValuationMethod, PhysicalCount
from django.apps import apps
import logging

logger = logging.getLogger(__name__)


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
        
        # ✅ Determinar la ubicación correcta
        location = movement.location_to or movement.location_from
        
        if not location:
            logger.warning(f"⚠️ Movimiento {movement.id} sin ubicación, no se actualiza inventario")
            return
        
        # ✅ Usar get_or_create con la ubicación correcta
        inventory, created = Inventory.objects.get_or_create(
            product=movement.product,
            location=location,
            company=movement.company,
            defaults={
                'quantity': 0,
                'average_cost': 0,
                'total_value': 0,
            }
        )
        
        logger.info(f"🔴 Actualizando inventario para {movement.product.name}")
        logger.info(f"   Ubicación: {location.code}")
        logger.info(f"   Tipo movimiento: {movement.type}")
        logger.info(f"   Cantidad: {movement.quantity}")
        logger.info(f"   Inventario existente: {created}")
        logger.info(f"   Cantidad actual: {inventory.quantity}")
        logger.info(f"   Compañía: {movement.company.code if movement.company else 'Sin compañía'}")
        
        # ✅ Actualizar cantidad según tipo de movimiento
        if movement.type == 'ENTRY':
            inventory.quantity += movement.quantity
            # Actualizar costo promedio (si tiene unit_price)
            if movement.unit_price:
                # Calcular nuevo costo promedio ponderado
                total_cost_before = (inventory.quantity - movement.quantity) * inventory.average_cost
                total_cost_new = movement.quantity * movement.unit_price
                new_total_quantity = inventory.quantity
                
                if new_total_quantity > 0:
                    inventory.average_cost = (total_cost_before + total_cost_new) / new_total_quantity
                else:
                    inventory.average_cost = movement.unit_price
                    
        elif movement.type == 'EXIT':
            if inventory.quantity < movement.quantity:
                raise ValidationError(f"Stock insuficiente para {movement.product.name}. "
                                     f"Disponible: {inventory.quantity}, Solicitado: {movement.quantity}")
            inventory.quantity -= movement.quantity
            
        elif movement.type == 'TRANSFER':
            # Para transferencias, ya se actualiza en dos movimientos separados
            pass
        
        # ✅ Actualizar valor total
        inventory.total_value = inventory.quantity * inventory.average_cost
        
        # ✅ Guardar el inventario (actualizar o crear)
        inventory.save()
        
        logger.info(f"   ✅ Inventario actualizado: {inventory.quantity} unidades")
        logger.info(f"   Costo promedio: {inventory.average_cost}")
        logger.info(f"   Valor total: {inventory.total_value}")
        
        return inventory
    
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
            defaults={
                'quantity': 0,
                'average_cost': 0,
                'total_value': 0,
                'company': count.company
            }
        )
        inventory.quantity = count.counted_quantity
        inventory.total_value = inventory.quantity * inventory.average_cost
        inventory.save()
        
        count.status = 'CONFIRMED'
        count.save()
        
        return count