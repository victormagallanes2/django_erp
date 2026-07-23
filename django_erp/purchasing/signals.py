# django_erp/purchasing/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import PurchaseOrder


@receiver(post_save, sender=PurchaseOrder)
def purchase_order_updated(sender, instance, **kwargs):
    """Cuando se actualiza una orden de compra, recalcular totales"""
    # Los totales ya se calculan en save_formset del admin
    # Esta señal es para futuras integraciones
    pass