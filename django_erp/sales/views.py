# sales/views.py
from django.contrib.admin.views.decorators import staff_member_required
from django_erp.accounting.services import CurrencyService
from django_erp.configuration.models import Currency
from django_erp.accounting.models import ExchangeRate
from decimal import Decimal
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST
from django.views.generic import TemplateView
from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from decimal import Decimal, ROUND_HALF_UP
from django_erp.inventory.models import Product, Inventory
from django_erp.configuration.models import Company, Currency, PaymentMethod
from django_erp.accounting.models import ExchangeRate
from django_erp.accounting.services import TaxService
from django_erp.inventory.services import WarehouseService, InventoryService
from django_erp.inventory.models import Location
from .models import SaleInvoice, SaleInvoiceLine, CashTransaction, Payment, Customer, CashRegister
from .helpers import get_open_register
from unfold.views import UnfoldModelAdminViewMixin
from django.urls import reverse
from django.contrib.admin.views.decorators import staff_member_required
from django import forms as dj_forms
from django.contrib.admin.widgets import AutocompleteSelect
from django.contrib import admin
import json
import logging
from django.db.models import Q

logger = logging.getLogger(__name__)

# ============================================================
# ✅ VISTA POS (interfaz)
# ============================================================



# views.py
from django.db.models import Q

@staff_member_required
@require_GET
def pos_customer_search(request):
    """Busca clientes por nombre o cédula/RIF para el POS."""
    query = request.GET.get('q', '').strip()
    company = getattr(request, 'current_company', None)
    if not company:
        company = Company.get_active()

    if not company:
        return JsonResponse({'results': []})

    qs = Customer.objects.filter(company=company, is_active=True)

    if query:
        qs = qs.filter(
            Q(name__icontains=query) | Q(tax_id__icontains=query)
        )

    qs = qs.order_by('name')[:20]

    results = [
        {
            'id': c.id,
            'name': c.name,
            'tax_id': c.tax_id or '',
            'text': f"{c.name} ({c.tax_id})" if c.tax_id else c.name,
        }
        for c in qs
    ]
    return JsonResponse({'results': results})


class POSView(UnfoldModelAdminViewMixin, TemplateView):
    title = "Facturación Rápida (POS)"
    permission_required = ('sales.add_saleinvoice',)
    template_name = "admin/sales/pos.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        company = getattr(self.request, 'current_company', None)
        if not company:
            company = Company.get_active()
        context['company'] = company
        context['company_name'] = company.name if company else "Sin compañía"

        rate = ExchangeRate.get_today_rate('USD', 'BS')
        context['exchange_rate'] = float(rate) if rate else 0

        context['payment_methods'] = PaymentMethod.objects.filter(
            company=company, is_active=True
        ) if company else PaymentMethod.objects.none()

        context['search_url'] = self.request.build_absolute_uri('search/')
        context['checkout_url'] = self.request.build_absolute_uri('checkout/')
        context['customer_search_url'] = self.request.build_absolute_uri('customer-search/')

        return context


# ============================================================
# ✅ ENDPOINT: Buscar productos (para el POS)
# ============================================================

@staff_member_required
@require_GET
def pos_search_products(request):
    """Busca productos por código o nombre para el POS"""
    query = request.GET.get('q', '').strip()
    company = getattr(request, 'current_company', None)
    if not company:
        company = Company.get_active()

    if not company:
        return JsonResponse({'results': []})

    qs = Product.objects.filter(company=company, is_active=True)

    if query:
        qs = qs.filter(code__icontains=query) | qs.filter(name__icontains=query)

    qs = qs[:20]  # Limitar resultados

    rate = ExchangeRate.get_today_rate('USD', 'BS') or Decimal('0')

    results = []
    for p in qs:
        # Stock total
        stock = Inventory.objects.filter(
            product=p, company=company
        ).aggregate(total=__import__('django.db.models', fromlist=['Sum']).Sum('quantity'))['total'] or 0

        # Primera ubicación con stock
        inventory_rec = Inventory.objects.filter(
            product=p, company=company, quantity__gt=0
        ).first()
        location_id = inventory_rec.location_id if inventory_rec and inventory_rec.location else None

        price_usd = Decimal(str(p.sale_price)) if p.sale_price else Decimal('0')
        price_bs = price_usd * rate

        results.append({
            'id': p.id,
            'code': p.code,
            'name': p.name,
            'price_usd': float(price_usd),
            'price_bs': float(price_bs),
            'stock': stock,
            'location_id': location_id,
            'is_service': getattr(p, 'is_service', False),
        })

    return JsonResponse({'results': results})


# ============================================================
# ✅ ENDPOINT: Checkout (crear factura desde el POS)
# ============================================================

@staff_member_required
@require_POST
def pos_checkout(request):
    """Crea una factura completa desde el POS"""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'JSON inválido'}, status=400)

    customer_id = data.get('customer_id')
    lines_data = data.get('lines', [])
    payment_method_id = data.get('payment_method_id')
    note = data.get('note', '')

    if not customer_id:
        return JsonResponse({'error': 'Debes seleccionar un cliente'}, status=400)
    if not lines_data:
        return JsonResponse({'error': 'El carrito está vacío'}, status=400)
    if not payment_method_id:
        return JsonResponse({'error': 'Debes seleccionar un método de pago'}, status=400)

    company = getattr(request, 'current_company', None)
    if not company:
        company = Company.get_active()
    if not company:
        return JsonResponse({'error': 'No hay compañía activa'}, status=400)

    try:
        with transaction.atomic():
            customer = Customer.objects.get(id=customer_id, company=company)
            payment_method = PaymentMethod.objects.get(id=payment_method_id, company=company)

            # ✅ 1. Verificar caja abierta
            try:
                register = get_open_register(request.user)
            except ValidationError as e:
                return JsonResponse({'error': str(e)}, status=400)

            # ✅ 2. Generar número de factura
            from datetime import datetime
            last_invoice = SaleInvoice.objects.order_by('-id').first()
            if last_invoice and last_invoice.number:
                try:
                    last_num = int(last_invoice.number.split('-')[-1])
                    next_num = last_num + 1
                except (ValueError, IndexError):
                    next_num = 1
            else:
                next_num = 1

            number = f"FAC-VENTA-{datetime.now().strftime('%Y%m')}-{next_num:04d}"

            # ✅ 3. Crear factura
            tax_rate = TaxService.get_current_vat_rate(company) if company else Decimal('16.00')

            invoice = SaleInvoice.objects.create(
                number=number,
                customer=customer,
                customer_name=customer.name,
                customer_tax_id=customer.tax_id,
                customer_address=customer.address,
                status='PAID',
                tax_rate=tax_rate,
                note=note,
                user=request.user,
                company=company,
            )

            # ✅ 4. Crear líneas
            for line_data in lines_data:
                product_id = line_data.get('product_id')
                quantity = int(line_data.get('quantity', 1))
                unit_price = Decimal(str(line_data.get('unit_price', 0)))
                location_id = line_data.get('location_id')

                product = Product.objects.get(id=product_id, company=company)

                SaleInvoiceLine.objects.create(
                    invoice=invoice,
                    product=product,
                    product_code=product.code,
                    product_name=product.name,
                    quantity=quantity,
                    unit_price=unit_price,
                    subtotal=quantity * unit_price,
                    company=company,
                )

                # ✅ 5. Reducir inventario (si no es servicio)
                if not getattr(product, 'is_service', False):
                    location = None
                    if location_id:
                        location = Location.objects.filter(id=location_id, company=company).first()
                    if not location:
                        # Buscar cualquier ubicación con stock
                        inv = Inventory.objects.filter(
                            product=product, company=company, quantity__gt=0
                        ).first()
                        location = inv.location if inv and inv.location else Location.objects.filter(
                            company=company, is_active=True
                        ).first()

                    if not location:
                        raise ValidationError(
                            f"No hay ubicación para el producto {product.name}"
                        )

                    stock = InventoryService.get_stock_by_location(
                        product.id, location.id, company
                    )
                    if stock < quantity:
                        raise ValidationError(
                            f"Stock insuficiente para '{product.name}'. "
                            f"Disponible: {stock}, Requerido: {quantity}"
                        )

                    WarehouseService.create_exit(
                        product_id=product.id,
                        quantity=quantity,
                        location_from_id=location.id,
                        unit_price=unit_price,
                        source_type='SALE',
                        source_reference=invoice.number,
                        note=f"Factura POS {invoice.number}",
                        user=request.user,
                        company=company,
                    )

            # ✅ 6. Recalcular totales
            invoice.calculate_totals()
            invoice.save()

            # ✅ 7. Registrar transacción en caja
            CashTransaction.objects.create(
                register=register,
                type='SALE',
                amount=invoice.total,
                description=f"Factura POS {invoice.number} - {customer.name}",
                reference=invoice.number,
                user=request.user,
                company=company,
            )
            register.calculate_totals()

            # ✅ 8. Crear pago
            currency = payment_method.default_currency or Currency.objects.filter(code='USD').first()
            if currency:
                Payment.objects.create(
                    sale_invoice=invoice,
                    method=payment_method,
                    currency=currency,
                    amount=invoice.total,
                    amount_usd=invoice.total,
                    reference=f"Pago POS {invoice.number}",
                    status='COMPLETED',
                    user=request.user,
                    company=company,
                )

            return JsonResponse({
                'success': True,
                'invoice_id': invoice.id,
                'invoice_number': invoice.number,
                'subtotal': float(invoice.subtotal),
                'tax': float(invoice.tax),
                'total': float(invoice.total),
                'customer_name': customer.name,
                'print_url': f'/admin/sales/saleinvoice/{invoice.id}/change/',
            })

    except Customer.DoesNotExist:
        return JsonResponse({'error': 'Cliente no encontrado'}, status=404)
    except PaymentMethod.DoesNotExist:
        return JsonResponse({'error': 'Método de pago no encontrado'}, status=404)
    except Product.DoesNotExist:
        return JsonResponse({'error': 'Producto no encontrado'}, status=404)
    except ValidationError as e:
        return JsonResponse({'error': str(e)}, status=400)
    except Exception as e:
        logger.exception("Error en POS checkout")
        return JsonResponse({'error': f'Error inesperado: {str(e)}'}, status=500)


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


class POSCustomerForm(dj_forms.ModelForm):
    class Meta:
        model = Customer
        fields = ['name', 'tax_id', 'email', 'phone', 'address']
        widgets = {
            'name': dj_forms.TextInput(attrs={'placeholder': 'Nombre completo'}),
            'tax_id': dj_forms.TextInput(attrs={'placeholder': 'V-12345678'}),
            'email': dj_forms.EmailInput(attrs={'placeholder': 'correo@ejemplo.com'}),
            'phone': dj_forms.TextInput(attrs={'placeholder': '0414-1234567'}),
            'address': dj_forms.Textarea(attrs={'rows': 2, 'placeholder': 'Dirección'}),
        }


@staff_member_required
def pos_customer_form(request):
    """Vista que devuelve SOLO el formulario de cliente para el POS."""
    if request.method == 'POST':
        form = POSCustomerForm(request.POST)
        if form.is_valid():
            customer = form.save(commit=False)
            company = getattr(request, 'current_company', None) or Company.get_active()
            customer.company = company
            customer.is_active = True
            customer.save()
            return JsonResponse({
                'success': True,
                'customer_id': customer.id,
                'customer_name': customer.name,
                'customer_tax_id': customer.tax_id,
            })
        # Si hay errores, devolver el form con errores
        return render(request, 'admin/sales/customer_form.html', {'form': form})

    form = POSCustomerForm()
    return render(request, 'admin/sales/customer_form.html', {'form': form})