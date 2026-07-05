# sales/signals.py
from django.db.models.signals import post_save
from django.dispatch import Signal
from .models import SaleOrder

# ✅ Señal que se emite cuando una orden se confirma
order_confirmed = Signal()


def on_order_status_change(sender, instance, created, **kwargs):
    """Detectar cuando el estado cambia a CONFIRMED"""
    if not created:
        try:
            old_instance = SaleOrder.objects.get(pk=instance.pk)
            if old_instance.status == 'DRAFT' and instance.status == 'CONFIRMED':
                order_confirmed.send(sender=SaleOrder, order=instance)
        except SaleOrder.DoesNotExist:
            pass


# ✅ Conectar la señal solo si Sales está instalado
try:
    post_save.connect(on_order_status_change, sender=SaleOrder)
except Exception as e:
    print(f"⚠️ Error connecting signal: {e}")