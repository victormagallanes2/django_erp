# sales/views.py
from django.http import JsonResponse
from django.contrib.admin.views.decorators import staff_member_required
from django.views.decorators.http import require_GET
from django_erp.warehouse.models import Product


@staff_member_required
@require_GET
def get_product_price(request):
    """Vista para obtener el precio y ubicación de un producto"""
    product_id = request.GET.get('product_id')
    
    if not product_id:
        return JsonResponse({'error': 'Product ID required'}, status=400)
    
    try:
        product = Product.objects.get(id=product_id)
        
        # ✅ Obtener la ubicación predeterminada del producto (si tiene)
        # Para este ejemplo, tomamos la primera ubicación donde tiene stock
        from django_erp.inventory.models import Inventory
        inventory = Inventory.objects.filter(product=product).first()
        
        response_data = {
            'unit_price': float(product.sale_price) if product.sale_price else 0,
            'product_name': product.name,
            'product_code': product.code,
        }
        
        if inventory and inventory.location:
            response_data['location_id'] = inventory.location.id
            response_data['location_code'] = inventory.location.code
        
        return JsonResponse(response_data)
    except Product.DoesNotExist:
        return JsonResponse({'error': 'Product not found'}, status=404)