# sales/signals.py - VERSIÓN SIMPLIFICADA (sin pre_save)
from django.db.models.signals import post_save
from django.dispatch import Signal, receiver
from .models import SaleOrder, CashTransaction, CashRegister
import logging

logger = logging.getLogger(__name__)

# Señal que se emite cuando una orden se confirma
order_confirmed = Signal()


@receiver(order_confirmed)
def register_sale_in_cash(sender, order, **kwargs):
    """Cuando se confirma una venta, registrarla en la caja abierta"""
    print(f"🔴 SIGNAL: register_sale_in_cash called for {order.number}")
    
    try:
        # ✅ Buscar caja abierta para este usuario
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
        
        # ✅ Verificar si ya existe transacción para esta orden
        existing = CashTransaction.objects.filter(
            reference=order.number,
            type='SALE'
        ).exists()
        
        if existing:
            print(f"   ⚠️ Transacción ya existe para {order.number}")
            return
        
        # ✅ Crear transacción
        print(f"   Creando transacción para {order.number}")
        transaction = CashTransaction.objects.create(
            register=register,
            type='SALE',
            amount=order.total,
            description=f"Venta {order.number} - {order.customer.name}",
            reference=order.number,
            user=user
        )
        print(f"   ✅ Transacción creada: {transaction.id}")
        
        # ✅ Recalcular totales de la caja
        register.calculate_totals()
        print(f"   ✅ Totales recalculados")
        print(f"      Total ventas: {register.total_sales}")
        print(f"      Total esperado: {register.expected_total}")
        logger.info(f"✅ Venta {order.number} registrada en caja {register.number}")
        
    except Exception as e:
        print(f"   ❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        logger.error(f"❌ Error al registrar venta en caja: {e}")