# invoicing/views.py
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.urls import reverse
from django.apps import apps
from .services import InvoiceService
from django_erp.configuration.models import ExchangeRate
from decimal import Decimal
from django_erp.warehouse.models import Product
from django.views.decorators.http import require_GET
from django.http import JsonResponse



@staff_member_required
def generate_invoice_from_order(request, order_id):
    """Vista para generar factura desde una orden de venta"""
    # ✅ Verificar que Sales está instalado
    if not apps.is_installed('django_erp.sales'):
        messages.error(request, "El módulo de ventas no está instalado")
        return redirect('admin:index')
    
    from django_erp.sales.models import SaleOrder
    
    order = get_object_or_404(SaleOrder, id=order_id)
    
    # Verificar que la orden esté confirmada
    if order.status != 'CONFIRMED':
        messages.error(request, "Solo se pueden facturar órdenes confirmadas")
        return redirect('admin:sales_saleorder_change', order_id)
    
    # Verificar que no tenga factura
    if hasattr(order, 'invoice') and order.invoice:
        messages.warning(request, "Esta orden ya tiene una factura")
        return redirect('admin:sales_saleorder_change', order_id)
    
    try:
        # Generar factura
        invoice = InvoiceService.create_invoice_from_sale_order(order.id, request.user)
        messages.success(request, f"Factura {invoice.number} creada exitosamente")
        return redirect('admin:invoicing_invoice_change', invoice.id)
    except Exception as e:
        messages.error(request, f"Error al generar factura: {str(e)}")
        return redirect('admin:sales_saleorder_change', order_id)



@staff_member_required
@require_GET
def get_product_price(request):
    """Vista para obtener el precio y ubicación de un producto (para facturación)"""
    product_id = request.GET.get('product_id')
    
    if not product_id:
        return JsonResponse({'error': 'Product ID required'}, status=400)
    
    try:
        product = Product.objects.get(id=product_id)
        
        price_usd = Decimal(str(product.price)) if product.price else Decimal('0')
        rate = ExchangeRate.get_today_rate('USD', 'BS')
        
        response_data = {
            'unit_price': float(price_usd),
            'price_usd_display': f"$ {float(price_usd):.2f}",
            'price_bs': float(price_usd * rate) if rate else float(price_usd),
            'price_bs_display': f"Bs. {float(price_usd * rate):.2f}" if rate else f"Bs. {float(price_usd):.2f}",
            'rate': float(rate) if rate else 0,
            'product_name': product.name,
            'product_code': product.code,
        }
        
        return JsonResponse(response_data)
    except Product.DoesNotExist:
        return JsonResponse({'error': 'Product not found'}, status=404)