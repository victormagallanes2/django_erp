# sales/signals.py
from django.db.models.signals import post_save
from django.dispatch import Signal
from .models import SaleOrder
from .models import SaleOrder, CashTransaction, CashRegister
from django.dispatch import receiver
import logging

logger = logging.getLogger(__name__)

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


@receiver(post_save, sender=SaleOrder)
def register_sale_in_cash(sender, instance, created, **kwargs):
    """Cuando se confirma una venta, registrarla en la caja abierta"""
    
    # ✅ SOLO cuando la orden se confirma (status cambia a CONFIRMED)
    if instance.status == 'CONFIRMED' and instance.user:
        try:
            # ✅ Verificar si ya existe transacción para esta orden
            existing = CashTransaction.objects.filter(
                reference=instance.number,
                type='SALE'
            ).exists()
            
            if existing:
                logger.info(f"ℹ️ Transacción ya existe para {instance.number}")
                return
            
            register = CashRegister.objects.get(
                user=instance.user,
                status='OPEN'
            )
            
            CashTransaction.objects.create(
                register=register,
                type='SALE',
                amount=instance.total,
                description=f"Venta {instance.number} - {instance.customer.name}",
                reference=instance.number,
                user=instance.user
            )
            
            register.calculate_totals()
            logger.info(f"✅ Venta {instance.number} registrada en caja")
            
        except CashRegister.DoesNotExist:
            logger.info(f"ℹ️ No hay caja abierta para {instance.user.username}")