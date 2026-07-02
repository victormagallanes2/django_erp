# warehouse/services.py
from django.db import transaction
from django.core.exceptions import ValidationError
from .models import Product, Location, Movement


class WarehouseService:
    """Servicios de gestión física del almacén"""
    
    @staticmethod
    @transaction.atomic
    def create_entry(product_id, quantity, location_to_id, source_type='MANUAL', source_reference='', note='', user=None):
        """Registrar entrada de mercancía a una ubicación"""
        product = Product.objects.get(id=product_id)
        location_to = Location.objects.get(id=location_to_id)
        
        if quantity <= 0:
            raise ValidationError("La cantidad debe ser mayor a cero")
        
        movement = Movement.objects.create(
            product=product,
            type='ENTRY',
            quantity=quantity,
            location_to=location_to,
            source_type=source_type,
            source_reference=source_reference,
            note=note,
            user=user
        )
        return movement
    
    @staticmethod
    @transaction.atomic
    def create_exit(product_id, quantity, location_from_id, source_type='MANUAL', source_reference='', note='', user=None):
        """Registrar salida de mercancía desde una ubicación"""
        product = Product.objects.get(id=product_id)
        location_from = Location.objects.get(id=location_from_id)
        
        if quantity <= 0:
            raise ValidationError("La cantidad debe ser mayor a cero")
        
        movement = Movement.objects.create(
            product=product,
            type='EXIT',
            quantity=quantity,
            location_from=location_from,
            source_type=source_type,
            source_reference=source_reference,
            note=note,
            user=user
        )
        return movement
    
    @staticmethod
    @transaction.atomic
    def create_transfer(product_id, quantity, location_from_id, location_to_id, note='', user=None):
        """Trasladar producto de una ubicación a otra"""
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
            location_from=location_from,
            location_to=location_to,
            note=note,
            user=user
        )
        return movement