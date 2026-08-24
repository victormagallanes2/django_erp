# inventory/views.py
from django.http import JsonResponse
from django.contrib.admin.views.decorators import staff_member_required
from django.views.decorators.http import require_GET
from django_erp.configuration.models import Company
from .models import Product, Inventory
from decimal import Decimal

@staff_member_required
@require_GET
def get_product_stock(request):
    """
    Vista para obtener el stock de un producto en una ubicación específica.
    """
    product_id = request.GET.get('product_id')
    location_id = request.GET.get('location_id')
    
    if not product_id:
        return JsonResponse({'error': 'Product ID required'}, status=400)
    
    try:
        product = Product.objects.get(id=product_id)
        company = getattr(request, 'current_company', None)
        if not company:
            company = Company.get_active()
        
        stock = 0
        location_id_int = None
        
        # Si se proporciona location_id, obtener el stock en esa ubicación
        if location_id:
            try:
                location_id_int = int(location_id)
                inventory = Inventory.objects.filter(
                    product=product, 
                    location_id=location_id_int,
                    company=company
                ).first()
                if inventory:
                    stock = inventory.quantity
            except (ValueError, TypeError):
                pass
        
        # Si no se proporcionó location_id o no hay stock, obtener stock total
        if not location_id or stock == 0:
            inventories = Inventory.objects.filter(product=product, company=company)
            for inv in inventories:
                stock += inv.quantity
        
        return JsonResponse({
            'stock': stock,
            'stock_display': f"{stock} unidades disponibles",
            'product_name': product.name,
        })
        
    except Product.DoesNotExist:
        return JsonResponse({'error': 'Product not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)