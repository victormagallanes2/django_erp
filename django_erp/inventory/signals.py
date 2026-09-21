# inventory/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Movement
from .services import InventoryService
import logging
from django.db import transaction

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Movement)
def movement_created(sender, instance, created, **kwargs):
    if not created:
        return
    
    # ✅ Ejecutar solo cuando la transacción externa haga commit exitoso
    transaction.on_commit(
        lambda: InventoryService.update_stock_from_movement(instance)
    )