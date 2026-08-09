# django_erp/purchasing/views.py
from django.http import JsonResponse
from django.contrib.admin.views.decorators import staff_member_required
from django.views.decorators.http import require_GET
from django_erp.inventory.models import Product
from django_erp.inventory.models import Inventory
from django_erp.configuration.models import ExchangeRate, Currency
from decimal import Decimal
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from .models import PurchaseOrder
from .services import PurchaseInvoiceService


@staff_member_required
@require_GET
def get_product_price(request):
    """
    Vista para obtener el precio y ubicación de un producto para compras
    Similar a la de ventas pero para el módulo de compras
    """
    product_id = request.GET.get('product_id')
    
    if not product_id:
        return JsonResponse({'error': 'Product ID required'}, status=400)
    
    try:
        product = Product.objects.get(id=product_id)
        inventory = Inventory.objects.filter(product=product).first()
        
        # ✅ Obtener el precio (en compras usamos el mismo precio del producto)
        price_usd = Decimal(str(product.price)) if product.price else Decimal('0')
        
        # ✅ Obtener tasa del día
        rate = ExchangeRate.get_today_rate('USD', 'BS')
        
        # ✅ Calcular precio en Bs.
        if rate:
            price_bs = price_usd * rate
        else:
            price_bs = price_usd
        
        # ✅ Preparar respuesta
        response_data = {
            'unit_price': float(price_usd),
            'price_usd_display': f"$ {float(price_usd):.2f}",
            'price_bs': float(price_bs),
            'price_bs_display': f"Bs. {float(price_bs):.2f}",
            'rate': float(rate) if rate else 0,
            'product_name': product.name,
            'product_code': product.code,
        }
        
        # ✅ Agregar ubicación si existe
        if inventory and inventory.location:
            response_data['location_id'] = inventory.location.id
            response_data['location_code'] = inventory.location.code
        
        return JsonResponse(response_data)
        
    except Product.DoesNotExist:
        return JsonResponse({'error': 'Product not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@staff_member_required
def generate_invoice_from_purchase_order(request, order_id):
    """Vista para generar factura manualmente desde una orden de compra"""
    order = get_object_or_404(PurchaseOrder, id=order_id)
    
    if order.status != 'RECEIVED':
        messages.error(request, "Solo se pueden facturar órdenes recibidas")
        return redirect('admin:purchasing_purchaseorder_change', order_id)
    
    if order.invoiced:
        messages.warning(request, "Esta orden ya tiene una factura")
        return redirect('admin:purchasing_purchaseorder_change', order_id)
    
    try:
        invoice = PurchaseInvoiceService.create_invoice_from_purchase_order(order.id, request.user)
        messages.success(request, f"✅ Factura de compra {invoice.number} generada exitosamente")
        return redirect('admin:purchasing_purchaseinvoice_change', invoice.id)
    except Exception as e:
        messages.error(request, f"❌ Error al generar factura: {str(e)}")
        return redirect('admin:purchasing_purchaseorder_change', order_id)