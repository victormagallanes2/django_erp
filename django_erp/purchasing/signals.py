# django_erp/purchasing/signals.py
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from .models import PurchaseOrder
import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender=PurchaseOrder)
def purchase_order_updated(sender, instance, **kwargs):
    """Cuando se actualiza una orden de compra"""
    pass


# ✅ SEÑAL: Cuando una orden se recibe, generar factura
@receiver(pre_save, sender=PurchaseOrder)
def generate_invoice_on_receive(sender, instance, **kwargs):
    """
    Generar factura de compra cuando la orden se recibe
    Esta señal se ejecuta ANTES de guardar, por eso usamos pre_save
    """
    # ✅ Solo si la orden ya existe (no es nueva)
    if not instance.pk:
        return
    
    try:
        # ✅ Obtener el estado anterior
        old = PurchaseOrder.objects.get(pk=instance.pk)
        old_status = old.status
        new_status = instance.status
        
        # ✅ Si el estado cambió a RECEIVED
        if old_status != 'RECEIVED' and new_status == 'RECEIVED':
            logger.info(f"🔴 Orden {instance.number} está cambiando a RECEIVED")
            
            # ✅ NO GENERAMOS LA FACTURA AQUÍ
            # La generamos en el admin después de que se complete el guardado
            # Para evitar el error "Solo se pueden facturar órdenes recibidas"
            # Usamos un flag para indicar que se debe generar después
            instance._generate_invoice_on_save = True
            
    except PurchaseOrder.DoesNotExist:
        pass


# ✅ SEÑAL: Después de guardar, si hay flag, generar factura
@receiver(post_save, sender=PurchaseOrder)
def generate_invoice_after_save(sender, instance, created, **kwargs):
    """
    Generar factura después de guardar si el flag está presente
    """
    if hasattr(instance, '_generate_invoice_on_save') and instance._generate_invoice_on_save:
        logger.info(f"📄 Generando factura para {instance.number} (post_save)")
        
        # ✅ Importar aquí para evitar importaciones circulares
        from .services import PurchaseInvoiceService
        
        try:
            # ✅ Verificar que no tenga factura
            if not instance.invoiced:
                invoice = PurchaseInvoiceService.create_invoice_from_purchase_order(
                    instance.id, 
                    instance.user
                )
                logger.info(f"✅ Factura {invoice.number} generada automáticamente (post_save)")
            else:
                logger.info(f"ℹ️ La orden {instance.number} ya tiene factura")
        except Exception as e:
            logger.error(f"❌ Error generando factura en post_save: {e}")
            import traceback
            traceback.print_exc()
        
        # ✅ Limpiar el flag para que no se ejecute de nuevo
        del instance._generate_invoice_on_save