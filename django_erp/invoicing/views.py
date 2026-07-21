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
from .models import Invoice, InvoiceLine
from datetime import datetime
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction
from django.views.decorators.http import require_http_methods
import json




@staff_member_required
@csrf_exempt
@require_http_methods(["POST"])
def sync_offline_invoice(request):
    """
    Sincronizar una factura creada offline
    Recibe un JSON con los datos de la factura
    """
    try:
        data = json.loads(request.body)
        
        # ✅ Verificar que la factura no exista ya (por UUID)
        if Invoice.objects.filter(uuid=data.get('uuid')).exists():
            return JsonResponse({
                'success': True,
                'message': 'Factura ya existe en el servidor',
                'already_exists': True
            })
        
        # ✅ Obtener empresa activa
        company = Company.get_active()
        if not company:
            return JsonResponse({
                'success': False,
                'error': 'No hay empresa configurada'
            }, status=400)
        
        # ✅ Generar número de factura
        with transaction.atomic():
            last_invoice = Invoice.objects.order_by('-id').first()
            date_str = datetime.now().strftime('%Y%m')
            
            if last_invoice and last_invoice.number:
                try:
                    parts = last_invoice.number.split('-')
                    last_num = int(parts[-1])
                    new_num = last_num + 1
                except (ValueError, IndexError):
                    new_num = 1
            else:
                new_num = 1
            
            number = f"{company.invoice_prefix}-{date_str}-{str(new_num).zfill(4)}"
            
            # ✅ Crear factura
            invoice = Invoice.objects.create(
                uuid=data.get('uuid'),
                number=number,
                company=company,
                issuer_rif=company.rif,
                issuer_name=company.name,
                issuer_address=company.address,
                customer_name=data.get('customer_name', ''),
                customer_rif=data.get('customer_rif', ''),
                customer_address=data.get('customer_address', ''),
                subtotal=data.get('subtotal', 0),
                tax=data.get('tax', 0),
                total=data.get('total', 0),
                tax_rate=data.get('tax_rate', 16),
                status='ISSUED',
                sync_status='SYNCED',
                device_id=data.get('device_id', ''),
                synced_at=datetime.now(),
                user=request.user,
                note=data.get('note', '')
            )
            
            # ✅ Crear líneas de factura
            for line_data in data.get('lines', []):
                InvoiceLine.objects.create(
                    invoice=invoice,
                    uuid=line_data.get('uuid'),
                    product_code=line_data.get('product_code', ''),
                    product_name=line_data.get('product_name', ''),
                    quantity=line_data.get('quantity', 1),
                    unit_price=line_data.get('unit_price', 0),
                    subtotal=line_data.get('subtotal', 0)
                )
            
            return JsonResponse({
                'success': True,
                'message': f'Factura {number} sincronizada',
                'invoice_id': invoice.id,
                'number': number
            })
            
    except json.JSONDecodeError as e:
        return JsonResponse({
            'success': False,
            'error': f'Error en formato JSON: {str(e)}'
        }, status=400)
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


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