# inventory/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Movement
from .services import InventoryService
import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Movement)
def movement_created(sender, instance, created, **kwargs):
    """Cuando se crea un movimiento físico, actualizar el inventario contable"""
    logger.info("=" * 80)
    logger.info("🔴 [movement_created] SEÑAL DISPARADA")
    logger.info(f"   Movement ID: {instance.id}")
    logger.info(f"   Created: {created}")
    logger.info(f"   Type: {instance.type}")
    logger.info(f"   Product: {instance.product.name}")
    logger.info(f"   Quantity: {instance.quantity}")
    logger.info(f"   Company: {instance.company.code if instance.company else 'N/A'}")
    
    if created:
        try:
            logger.info("   🔄 Llamando a InventoryService.update_stock_from_movement()")
            InventoryService.update_stock_from_movement(instance)
            logger.info("   ✅ Inventario actualizado exitosamente")
        except Exception as e:
            logger.error(f"   ❌ Error actualizando inventario: {e}")
            import traceback
            logger.error(f"   Traceback: {traceback.format_exc()}")
    else:
        logger.info("   ℹ️ Movimiento no es nuevo, no se actualiza inventario")
    
    logger.info("=" * 80)