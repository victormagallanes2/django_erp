from django.http import JsonResponse
from django.contrib.admin.views.decorators import staff_member_required
from django.views.decorators.http import require_GET
from .models import Inventory


@staff_member_required
@require_GET
def get_available_quantity(request):
    """Vista AJAX para obtener la cantidad disponible de un producto en una ubicación"""
    product_id = request.GET.get('product_id')
    location_id = request.GET.get('location_id')
    
    if not product_id or not location_id:
        return JsonResponse({'error': 'Faltan parámetros'}, status=400)
    
    try:
        # Obtener la compañía activa
        company = getattr(request, 'current_company', None)
        
        # Buscar el inventario
        inventory = Inventory.objects.filter(
            product_id=product_id,
            location_id=location_id,
            company=company
        ).first()
        
        quantity = inventory.quantity if inventory else 0
        
        return JsonResponse({
            'quantity': quantity,
            'product_id': product_id,
            'location_id': location_id
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
