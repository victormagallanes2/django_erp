# inventory/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.apps import apps

# ✅ No importamos Movement directamente
# ✅ Usamos get_model para resolver dinámicamente


@receiver(post_save, sender='warehouse.Movement')
def movement_created(sender, instance, created, **kwargs):
    """Cuando se crea un movimiento físico, actualizar el inventario contable"""
    if created:
        from .services import InventoryService
        InventoryService.update_stock_from_movement(instance)