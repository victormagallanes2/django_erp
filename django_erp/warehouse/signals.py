# warehouse/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Movement
import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Movement)
def movement_created(sender, instance, created, **kwargs):
    """Cuando se crea un movimiento físico, actualizar el inventario contable"""
    if created:
        try:
            from inventory.services import InventoryService
            logger.info(f"🔄 Actualizando inventario desde movimiento {instance.id}")
            InventoryService.update_stock_from_movement(instance)
        except Exception as e:
            logger.error(f"❌ Error actualizando inventario desde movimiento {instance.id}: {e}")
            # No lanzar excepción para no romper la transacción
            # El movimiento ya se creó, pero el inventario quedó inconsistente