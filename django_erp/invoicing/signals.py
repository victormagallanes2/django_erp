# invoicing/signals.py
from django.dispatch import receiver
from django.apps import apps
import logging

logger = logging.getLogger(__name__)


# ✅ Intentar importar la señal de Sales
try:
    from django_erp.sales.signals import order_confirmed
    print("✅ order_confirmed importada desde Sales")
except ImportError as e:
    print(f"⚠️ Sales no disponible: {e}")
    order_confirmed = None


if order_confirmed:
    @receiver(order_confirmed)
    def on_order_confirmed(sender, order, **kwargs):
        """Cuando una orden se confirma, generar factura automáticamente"""
        print(f"🔔 Recibida señal para orden {order.number}")
        try:
            from .services import InvoiceService
            from django_erp.configuration.models import Company
            
            # Verificar que hay empresa configurada
            company = Company.get_active()
            if not company:
                print("❌ No hay empresa configurada")
                return
            
            invoice = InvoiceService.create_invoice_from_sale_order(order.id, order.user)
            print(f"✅ Factura {invoice.number} generada para {order.number}")
        except Exception as e:
            print(f"❌ Error al generar factura para {order.number}: {e}")
else:
    print("⚠️ order_confirmed no disponible")