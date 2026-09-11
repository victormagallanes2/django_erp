# rrhh/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings
from .models import Employee
from .services import CommissionService
import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def handle_employee_on_user_change(sender, instance, **kwargs):
    """Crear Employee automáticamente si el usuario se marca como empleado"""
    if instance.is_employee and not hasattr(instance, 'employee'):
        Employee.objects.create(user=instance)


@receiver(post_save, sender='sales.SaleInvoice')
def create_commission_on_invoice_paid(sender, instance, **kwargs):
    """
    ✅ Cuando una factura se marca como PAID, generar comisión.
    """
    if instance.status != 'PAID':
        return
    
    logger.info("=" * 80)
    logger.info(f"🔴 [create_commission_on_invoice_paid] Factura {instance.number} PAGADA")
    
    try:
        CommissionService.create_commission_for_invoice(instance)
    except Exception as e:
        logger.error(f"   ❌ Error creando comisión: {e}")
        import traceback
        logger.error(f"   Traceback: {traceback.format_exc()}")
    
    logger.info("=" * 80)