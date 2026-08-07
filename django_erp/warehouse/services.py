# warehouse/services.py
from django.db import transaction
from django.core.exceptions import ValidationError
from .models import Product, Location, Movement
from django_erp.configuration.models import Company
import logging

logger = logging.getLogger(__name__)


class WarehouseService:
    """Servicios de gestión física del almacén"""
    
    @staticmethod
    @transaction.atomic
    def create_entry(product_id, quantity, location_to_id, source_type='MANUAL', 
                     source_reference='', note='', user=None, unit_price=0):
        """Registrar entrada de mercancía a una ubicación"""
        # ✅ Obtener la compañía activa
        company = Company.get_active()
        if not company:
            raise ValidationError("No hay una compañía activa para este movimiento.")
        
        logger.info(f"🔴 CREANDO ENTRADA para compañía {company.code}")
        logger.info(f"   Producto ID: {product_id}")
        logger.info(f"   Cantidad: {quantity}")
        logger.info(f"   Ubicación destino ID: {location_to_id}")
        logger.info(f"   Precio unitario: {unit_price}")
        
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
            company=company,  # ← ✅ Asignar compañía
        )
        
        logger.info(f"   ✅ Movimiento creado: ID {movement.id} para compañía {company.code}")
        return movement
    
    @staticmethod
    @transaction.atomic
    def create_exit(product_id, quantity, location_from_id, source_type='MANUAL', 
                    source_reference='', note='', user=None, unit_price=0):
        """Registrar salida de mercancía desde una ubicación"""
        # ✅ Obtener la compañía activa
        company = Company.get_active()
        if not company:
            raise ValidationError("No hay una compañía activa para este movimiento.")
        
        logger.info(f"🔴 CREANDO SALIDA para compañía {company.code}")
        logger.info(f"   Producto ID: {product_id}")
        logger.info(f"   Cantidad: {quantity}")
        logger.info(f"   Ubicación origen ID: {location_from_id}")
        logger.info(f"   Precio unitario: {unit_price}")
        
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
            company=company,  # ← ✅ Asignar compañía
        )
        
        logger.info(f"   ✅ Movimiento creado: ID {movement.id} para compañía {company.code}")
        return movement
    
    @staticmethod
    @transaction.atomic
    def create_transfer(product_id, quantity, location_from_id, location_to_id, 
                        note='', user=None, unit_price=0):
        """Trasladar producto de una ubicación a otra"""
        # ✅ Obtener la compañía activa
        company = Company.get_active()
        if not company:
            raise ValidationError("No hay una compañía activa para este movimiento.")
        
        logger.info(f"🔴 CREANDO TRASLADO para compañía {company.code}")
        logger.info(f"   Producto ID: {product_id}")
        logger.info(f"   Cantidad: {quantity}")
        logger.info(f"   Ubicación origen ID: {location_from_id}")
        logger.info(f"   Ubicación destino ID: {location_to_id}")
        
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
            company=company,  # ← ✅ Asignar compañía
        )
        
        logger.info(f"   ✅ Movimiento creado: ID {movement.id} para compañía {company.code}")
        return movement