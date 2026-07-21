# invoicing/signals.py
from django.apps import apps
from django.dispatch import receiver
import logging

logger = logging.getLogger(__name__)

if apps.is_installed('django_erp.sales'):
    try:
        from django_erp.sales.signals import order_confirmed
        
        @receiver(order_confirmed)
        def on_order_confirmed(sender, order, **kwargs):
            """✅ ÚNICA señal que crea la factura"""
            try:
                from .services import InvoiceService
                
                print(f"🔴 Creando factura para orden {order.number}")
                
                # ✅ ✅ ✅ Verificar si la orden YA tiene factura
                if hasattr(order, 'invoice') and order.invoice:
                    print(f"   ⚠️ La orden {order.number} YA tiene factura")
                    return
                
                # ✅ ✅ ✅ Verificar si ya se creó una factura para esta orden
                from django_erp.invoicing.models import Invoice
                existing = Invoice.objects.filter(
                    sale_order_number=order.number
                ).exists()
                
                if existing:
                    print(f"   ⚠️ Ya existe una factura para la orden {order.number}")
                    return
                
                # ✅ Crear factura
                invoice = InvoiceService.create_invoice_from_sale_order(order.id)
                print(f"   ✅ Factura {invoice.number} creada")
                logger.info(f'✅ Factura {invoice.number} generada para {order.number}')
                
            except Exception as e:
                print(f"   ❌ ERROR: {e}")
                import traceback
                traceback.print_exc()
                logger.error(f'❌ Error al generar factura para {order.number}: {e}')
        
        print('✅ Invoicing signals conectadas a Sales')
        
    except ImportError as e:
        print(f'⚠️ Error: {e}')
else:
    print('ℹ️ Sales no está instalado')