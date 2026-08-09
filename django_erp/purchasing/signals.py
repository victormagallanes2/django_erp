# django_erp/purchasing/signals.py
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from .models import PurchaseOrder
import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender=PurchaseOrder)
def purchase_order_updated(sender, instance, **kwargs):
    """Cuando se actualiza una orden de compra"""
    # Solo log, no hacer nada más
    pass


# ✅ SEÑAL DESHABILITADA - Ahora la factura se genera en finalize_receipt
# @receiver(pre_save, sender=PurchaseOrder)
# def generate_invoice_on_receive(sender, instance, **kwargs):
#     pass


# ✅ SEÑAL DESHABILITADA - Ahora la factura se genera en finalize_receipt
# @receiver(post_save, sender=PurchaseOrder)
# def generate_invoice_after_save(sender, instance, created, **kwargs):
#     pass