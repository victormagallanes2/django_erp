# inventory/services.py
from django.db import transaction
from django.core.exceptions import ValidationError
from .models import Inventory, ValuationMethod, PhysicalCount, Product, Location, Movement
from django_erp.configuration.models import Company
import logging

logger = logging.getLogger(__name__)


# ============================================================
# SERVICIOS DE ALMACÉN (ANTIGUO WAREHOUSE)
# ============================================================

class WarehouseService:
    """Servicios de gestión física del almacén"""

    @staticmethod
    def get_or_create_default_location(company):
        """Obtener o crear una ubicación por defecto para la compañía"""
        if not company:
            return None
        
        default_location = Location.objects.filter(
            company=company,
            is_active=True
        ).first()
        
        if not default_location:
            default_location = Location.objects.create(
                code=f"ALM-{company.code}",
                name=f"Almacén Principal - {company.name}",
                description=f"Almacén principal de {company.name}",
                company=company,
                is_active=True
            )
            logger.info(f"✅ Creada ubicación por defecto para {company.code}: {default_location.code}")
        
        return default_location

    @staticmethod
    @transaction.atomic
    def create_entry(product_id, quantity, location_to_id, source_type='MANUAL', 
                     source_reference='', note='', user=None, unit_price=0, company=None):
        """Registrar entrada de mercancía a una ubicación"""
        
        if company is None:
            company = Company.get_active()
            if not company:
                raise ValidationError("No hay una compañía activa para este movimiento.")
            logger.warning(f"⚠️ No se pasó compañía a create_entry, usando fallback: {company.code}")
        
        logger.info(f"🔴 CREANDO ENTRADA para compañía {company.code}")
        
        product = Product.objects.get(id=product_id)
        location_to = Location.objects.get(id=location_to_id)
        
        if quantity <= 0:
            raise ValidationError("La cantidad debe ser mayor a cero")
        
        movement = Movement.objects.create(
            product=product,
            type='ENTRY',
            quantity=quantity,
            unit_price=unit_price,
            location_to=location_to,
            source_type=source_type,
            source_reference=source_reference,
            note=note,
            user=user,
            company=company,
        )
        
        logger.info(f"   ✅ Movimiento creado: ID {movement.id}")
        return movement
    
    @staticmethod
    @transaction.atomic
    def create_exit(product_id, quantity, location_from_id, source_type='MANUAL', 
                    source_reference='', note='', user=None, unit_price=0, company=None):
        """Registrar salida de mercancía desde una ubicación"""
        
        if company is None:
            company = Company.get_active()
            if not company:
                raise ValidationError("No hay una compañía activa para este movimiento.")
            logger.warning(f"⚠️ No se pasó compañía a create_exit, usando fallback: {company.code}")
        
        logger.info(f"🔴 CREANDO SALIDA para compañía {company.code}")
        
        product = Product.objects.get(id=product_id)
        location_from = Location.objects.get(id=location_from_id)
        
        if quantity <= 0:
            raise ValidationError("La cantidad debe ser mayor a cero")
        
        movement = Movement.objects.create(
            product=product,
            type='EXIT',
            quantity=quantity,
            unit_price=unit_price,
            location_from=location_from,
            source_type=source_type,
            source_reference=source_reference,
            note=note,
            user=user,
            company=company,
        )
        
        logger.info(f"   ✅ Movimiento creado: ID {movement.id}")
        return movement
    
    @staticmethod
    @transaction.atomic
    def create_transfer(product_id, quantity, location_from_id, location_to_id, 
                        note='', user=None, unit_price=0, company=None):
        """Trasladar producto de una ubicación a otra"""
        
        if company is None:
            company = Company.get_active()
            if not company:
                raise ValidationError("No hay una compañía activa para este movimiento.")
            logger.warning(f"⚠️ No se pasó compañía a create_transfer, usando fallback: {company.code}")
        
        logger.info(f"🔴 CREANDO TRASLADO para compañía {company.code}")
        
        product = Product.objects.get(id=product_id)
        location_from = Location.objects.get(id=location_from_id)
        location_to = Location.objects.get(id=location_to_id)
        
        if quantity <= 0:
            raise ValidationError("La cantidad debe ser mayor a cero")
        
        if location_from == location_to:
            raise ValidationError("Origen y destino no pueden ser la misma ubicación")
        
        movement = Movement.objects.create(
            product=product,
            type='TRANSFER',
            quantity=quantity,
            unit_price=unit_price,
            location_from=location_from,
            location_to=location_to,
            note=note,
            user=user,
            company=company,
        )
        
        logger.info(f"   ✅ Movimiento creado: ID {movement.id}")
        return movement


# ============================================================
# SERVICIOS DE INVENTARIO CONTABLE
# ============================================================

class InventoryService:
    """Servicios de gestión contable de inventario"""
    
    @staticmethod
    def get_stock_by_location(product_id, location_id, company=None):
        """Obtener stock de un producto en una ubicación específica"""
        try:
            queryset = Inventory.objects.filter(product_id=product_id, location_id=location_id)
            if company:
                queryset = queryset.filter(company=company)
            
            inventory = queryset.first()
            
            if inventory:
                logger.info(f"🔴 Stock encontrado: {inventory.quantity} para producto {product_id} en ubicación {location_id}")
                return inventory.quantity
            else:
                logger.info(f"🔴 No hay stock para producto {product_id} en ubicación {location_id}")
                return 0
        except Exception as e:
            logger.error(f"❌ Error obteniendo stock: {e}")
            return 0
    
    @staticmethod
    def get_total_stock(product_id, company=None):
        """Obtener stock total de un producto en todas las ubicaciones"""
        queryset = Inventory.objects.filter(product_id=product_id)
        if company:
            queryset = queryset.filter(company=company)
        return sum(inv.quantity for inv in queryset) if queryset else 0
    
    @staticmethod
    @transaction.atomic
    def update_stock_from_movement(movement):
        """Actualizar inventario desde un movimiento físico"""
        location = movement.location_to or movement.location_from
        
        if not location:
            logger.warning(f"⚠️ Movimiento {movement.id} sin ubicación, no se actualiza inventario")
            return
        
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
        
        if movement.type == 'ENTRY':
            inventory.quantity += movement.quantity
            if movement.unit_price:
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
            pass
        
        inventory.total_value = inventory.quantity * inventory.average_cost
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
        
        inventory, created = Inventory.objects.get_or_create(
            product=count.product,
            location=count.location,
            company=count.company,
            defaults={
                'quantity': 0,
                'average_cost': 0,
                'total_value': 0,
            }
        )
        inventory.quantity = count.counted_quantity
        inventory.total_value = inventory.quantity * inventory.average_cost
        inventory.save()
        
        count.status = 'CONFIRMED'
        count.save()
        
        return count