# sales/views.py
from django.http import JsonResponse
from django.contrib.admin.views.decorators import staff_member_required
from django.views.decorators.http import require_GET
from django_erp.warehouse.models import Product
from django_erp.inventory.models import Inventory
from django_erp.configuration.services import CurrencyService
from django_erp.configuration.models import ExchangeRate, Currency
from decimal import Decimal
from .models import CashRegister
from django.shortcuts import render


@staff_member_required
@require_GET
def get_product_price(request):
    """Vista para obtener el precio y ubicación de un producto"""
    product_id = request.GET.get('product_id')
    
    if not product_id:
        return JsonResponse({'error': 'Product ID required'}, status=400)
    
    try:
        product = Product.objects.get(id=product_id)
        inventory = Inventory.objects.filter(product=product).first()
        
        # ✅ Convertir a Decimal
        price_usd = Decimal(str(product.price)) if product.price else Decimal('0')
        
        # ✅ Obtener tasa del día
        rate = ExchangeRate.get_today_rate('USD', 'BS')
        print(f"💰 Tasa obtenida: {rate}")  # Log para depuración
        
        # ✅ Multiplicar Decimal con Decimal
        if rate:
            price_bs = price_usd * rate
        else:
            price_bs = price_usd
        
        # ✅ Convertir a float para JSON
        response_data = {
            'unit_price': float(price_usd),
            'price_usd_display': f"$ {float(price_usd):.2f}",
            'price_bs': float(price_bs),
            'price_bs_display': f"Bs. {float(price_bs):.2f}",
            'rate': float(rate) if rate else 0,
            'product_name': product.name,
            'product_code': product.code,
        }
        
        if inventory and inventory.location:
            response_data['location_id'] = inventory.location.id
            response_data['location_code'] = inventory.location.code
        
        return JsonResponse(response_data)
    except Product.DoesNotExist:
        return JsonResponse({'error': 'Product not found'}, status=404)



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