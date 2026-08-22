# sales/views.py
from django.http import JsonResponse
from django.contrib.admin.views.decorators import staff_member_required
from django.views.decorators.http import require_GET
from django_erp.inventory.models import Product
from django_erp.inventory.models import Inventory
from django_erp.configuration.services import CurrencyService
from django_erp.configuration.models import ExchangeRate, Currency
from decimal import Decimal
from .models import CashRegister
from django.shortcuts import render


@staff_member_required
@require_GET
def get_product_price(request):
    """Vista para obtener el precio y stock de un producto"""
    product_id = request.GET.get('product_id')
    
    if not product_id:
        return JsonResponse({'error': 'Product ID required'}, status=400)
    
    try:
        product = Product.objects.get(id=product_id)
        
        # ✅ Obtener el stock total del producto
        company = getattr(request, 'current_company', None)
        if not company:
            from django_erp.configuration.models import Company
            company = Company.get_active()
        
        # Calcular stock total sumando todas las ubicaciones
        stock_total = 0
        inventories = Inventory.objects.filter(product=product, company=company)
        for inv in inventories:
            stock_total += inv.quantity
        
        # ✅ Obtener el precio en USD
        price_usd = Decimal(str(product.sale_price)) if product.sale_price else Decimal('0')
        
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
            'stock': stock_total,  # ✅ Cantidad disponible en stock
            'stock_display': f"{stock_total} {product.get_unit_display()}" if stock_total > 0 else "Sin stock",
        }
        
        # ✅ Agregar ubicación si existe (para la primera ubicación)
        first_inventory = inventories.first()
        if first_inventory and first_inventory.location:
            response_data['location_id'] = first_inventory.location.id
            response_data['location_code'] = first_inventory.location.code
        
        return JsonResponse(response_data)
        
    except Product.DoesNotExist:
        return JsonResponse({'error': 'Product not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)



@staff_member_required
def cash_register_status(request):
    """Vista para ver el estado de la caja del usuario actual"""
    register = CashRegister.objects.filter(
        user=request.user,
        status='OPEN'
    ).first()
    
    context = {
        'register': register,
        'has_open_register': register is not None,
    }
    
    return render(request, 'admin/sales/cash_register_status.html', context)