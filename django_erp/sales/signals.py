# sales/signals.py
from django.db.models.signals import post_save
from django.dispatch import Signal, receiver
from .models import SaleOrder, CashTransaction, CashRegister
import logging

logger = logging.getLogger(__name__)

# Señal que se emite cuando una orden se confirma
order_confirmed = Signal()


@receiver(post_save, sender=SaleOrder)
def detect_order_status_change(sender, instance, created, **kwargs):
    """
    Detecta cuando una orden cambia de DRAFT a CONFIRMED
    ✅ Usa una bandera para evitar duplicados
    """
    # ✅ Si es una orden nueva, no hacer nada
    if created:
        return
    
    # ✅ ✅ ✅ BANDERA: Si ya se emitió la señal, no repetir
    if hasattr(instance, '_order_confirmed_signal_sent'):
        return
    
    try:
        # ✅ Obtener el estado anterior
        old_instance = SaleOrder.objects.get(pk=instance.pk)
        
        # ✅ Si pasó de DRAFT a CONFIRMED
        if old_instance.status == 'DRAFT' and instance.status == 'CONFIRMED':
            print(f"🔴 Orden {instance.number} confirmada (post_save)")
            
            # ✅ ✅ ✅ MARCAR como enviada
            instance._order_confirmed_signal_sent = True
            
            # ✅ Emitir señal
            order_confirmed.send(sender=SaleOrder, order=instance)
            print(f"   ✅ Señal emitida")
            
    except SaleOrder.DoesNotExist:
        pass


@receiver(order_confirmed)
def register_sale_in_cash(sender, order, **kwargs):
    """Cuando se confirma una venta, registrarla en la caja abierta"""
    print(f"🔴 SIGNAL: register_sale_in_cash called for {order.number}")
    
    try:
        user = getattr(order, '_status_changed_by', order.user)
        print(f"   Usuario: {user}")
        
        register = CashRegister.objects.filter(
            user=user,
            status='OPEN'
        ).first()
        
        if not register:
            print(f"   ❌ No hay caja abierta para {user.username}")
            logger.warning(f"⚠️ No hay caja abierta para {user.username}")
            return
        
        print(f"   ✅ Caja encontrada: {register.number}")
        
        existing = CashTransaction.objects.filter(
            reference=order.number,
            type='SALE'
        ).exists()
        
        if existing:
            print(f"   ⚠️ Transacción ya existe para {order.number}")
            return
        
        transaction = CashTransaction.objects.create(
            register=register,
            type='SALE',
            amount=order.total,
            description=f"Venta {order.number} - {order.customer.name}",
            reference=order.number,
            user=user
        )
        print(f"   ✅ Transacción creada: {transaction.id}")
        
        register.calculate_totals()
        print(f"   ✅ Totales recalculados")
        logger.info(f"✅ Venta {order.number} registrada en caja {register.number}")
        
    except Exception as e:
        print(f"   ❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        logger.error(f"❌ Error al registrar venta en caja: {e}")