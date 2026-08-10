# sales/signals.py - CON SEÑALES PARA CREAR NOTAS DE ENTREGA Y SEÑAL order_confirmed
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver, Signal
from django.core.exceptions import ValidationError
from .models import SaleOrder
from .services import SaleService
import logging

logger = logging.getLogger(__name__)

# ✅ SEÑAL PARA CUANDO UNA ORDEN ES CONFIRMADA
order_confirmed = Signal()


@receiver(pre_save, sender=SaleOrder)
def check_status_transition(sender, instance, **kwargs):
    """
    ✅ Validar transiciones de estado antes de guardar.
    """
    if not instance.pk:
        return
    
    try:
        old = SaleOrder.objects.get(pk=instance.pk)
        if old.status != instance.status:
            if not SaleService.can_transition(instance, instance.status, old.status):
                raise ValidationError(
                    f"No se puede cambiar de '{old.get_status_display()}' a "
                    f"'{instance.get_status_display()}'"
                )
    except SaleOrder.DoesNotExist:
        pass


@receiver(post_save, sender=SaleOrder)
def create_delivery_note_on_confirm(sender, instance, created, **kwargs):
    """
    ✅ Cuando una venta se confirma, crear una Nota de Entrega en Borrador.
    """
    # Solo ejecutar si el estado cambió a CONFIRMED
    if instance.pk:
        try:
            old = SaleOrder.objects.get(pk=instance.pk)
            # Si el estado cambió a CONFIRMED y antes no lo estaba
            if old.status != 'CONFIRMED' and instance.status == 'CONFIRMED':
                logger.info("=" * 80)
                logger.info(f"🔴 [create_delivery_note_on_confirm] Orden {instance.number} confirmada")
                logger.info("   🔄 Creando nota de entrega...")
                
                # Llamar al servicio para crear la nota de entrega
                # Pero solo si no se ha creado ya (evitar duplicados)
                from django_erp.inventory.models import DeliveryNote
                existing = DeliveryNote.objects.filter(
                    customer=instance.customer,
                    customer_name=instance.customer.name,
                    notes__icontains=f"Venta {instance.number}",
                    company=instance.company,
                    status='DRAFT'
                ).first()
                
                if not existing:
                    SaleService.confirm_order(instance, instance.user)
                    logger.info(f"   ✅ Nota de entrega creada para orden {instance.number}")
                else:
                    logger.info(f"   ℹ️ Nota de entrega ya existe para orden {instance.number}")
                logger.info("=" * 80)
        except SaleOrder.DoesNotExist:
            pass