# invoicing/signals.py
from django.apps import apps
import logging

logger = logging.getLogger(__name__)


# ✅ Verificar si Sales está instalado antes de importar
if apps.is_installed('django_erp.sales'):
    try:
        from django_erp.sales.signals import order_confirmed
        from django.dispatch import receiver
        
        @receiver(order_confirmed)
        def on_order_confirmed(sender, order, **kwargs):
            """Cuando una orden se confirma, generar factura automáticamente"""
            try:
                from .services import InvoiceService
                invoice = InvoiceService.create_invoice_from_sale_order(order.id, order.user)
                logger.info(f"✅ Factura {invoice.number} generada para {order.number}")
            except Exception as e:
                logger.error(f"❌ Error al generar factura para {order.number}: {e}")
        
        logger.info("✅ Signals de Invoicing conectadas a Sales")
    except ImportError as e:
        logger.warning(f"⚠️ No se pudieron conectar signals: {e}")
else:
    logger.info("ℹ️ Sales no está instalado. Invoicing funciona en modo independiente.")