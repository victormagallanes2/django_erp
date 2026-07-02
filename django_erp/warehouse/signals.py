# warehouse/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Movement
from inventory.services import InventoryService  # ← Importar desde inventory


@receiver(post_save, sender=Movement)
def movement_created(sender, instance, created, **kwargs):
    """Cuando se crea un movimiento físico, actualizar el inventario contable"""
    if created:
        # Llamar al servicio de inventario para actualizar el stock
        InventoryService.update_stock_from_movement(instance)