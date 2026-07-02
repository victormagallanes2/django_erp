# invoicing/views.py
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.urls import reverse
from django.apps import apps
from .services import InvoiceService


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