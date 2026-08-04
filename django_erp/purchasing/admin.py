# django_erp/purchasing/admin.py - Reemplazar completamente el admin

from django.contrib import admin
from django import forms
from django.utils.html import format_html
from django.contrib import messages
from django.core.exceptions import ValidationError
from unfold.admin import ModelAdmin as UnfoldModelAdmin
from unfold.admin import TabularInline as UnfoldTabularInline
from .models import Supplier, PurchaseOrder, PurchaseLine, PurchasePayment
from decimal import Decimal, ROUND_HALF_UP
from django_erp.configuration.models import ExchangeRate, Company
import logging
import traceback
from .models import PurchaseInvoice, PurchaseInvoiceLine

logger = logging.getLogger(__name__)


@admin.register(Supplier)
class SupplierAdmin(UnfoldModelAdmin):
    list_display = ['name', 'tax_id', 'email', 'phone', 'is_active']
    list_filter = ['is_active']
    search_fields = ['name', 'tax_id', 'email', 'phone']
    
    fieldsets = (
        ('Información', {
            'fields': ('name', 'tax_id', 'email', 'phone', 'address')
        }),
        ('Estado', {
            'fields': ('is_active',)
        }),
    )
    readonly_fields = ['created_at', 'updated_at']


class PurchaseLineInline(UnfoldTabularInline):
    """Inline de líneas de compra"""
    model = PurchaseLine
    extra = 0
    fields = ['product', 'location', 'quantity', 'unit_price', 'subtotal']
    readonly_fields = ['subtotal']
    autocomplete_fields = ['product']
    
    def get_formset(self, request, obj=None, **kwargs):
        formset = super().get_formset(request, obj, **kwargs)
        from django_erp.warehouse.models import Product, Location
        formset.form.base_fields['product'].queryset = Product.objects.filter(is_active=True)
        formset.form.base_fields['location'].queryset = Location.objects.filter(is_active=True)
        formset.form.base_fields['unit_price'].initial = Decimal('0.00')
        formset.form.base_fields['quantity'].initial = 1
        return formset
    
    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.select_related('product')


class PurchaseOrderForm(forms.ModelForm):
    """Formulario de orden de compra"""
    
    # Campos para mostrar totales
    subtotal_display = forms.CharField(
        required=False,
        disabled=True,
        label="Subtotal (USD)",
        initial="0.00"
    )
    
    tax_display = forms.CharField(
        required=False,
        disabled=True,
        label="IVA (USD)",
        initial="0.00"
    )
    
    total_display = forms.CharField(
        required=False,
        disabled=True,
        label="Total (USD)",
        initial="0.00"
    )
    
    subtotal_bs_display = forms.CharField(
        required=False,
        disabled=True,
        label="Subtotal (Bs.)",
        initial="0.00"
    )
    
    tax_bs_display = forms.CharField(
        required=False,
        disabled=True,
        label="IVA (Bs.)",
        initial="0.00"
    )
    
    total_bs_display = forms.CharField(
        required=False,
        disabled=True,
        label="Total (Bs.)",
        initial="0.00",
        help_text="Convertido según tasa del día"
    )
    
    rate_display = forms.CharField(
        required=False,
        disabled=True,
        label="Tasa del día",
        initial="1 USD = Bs. 0.00"
    )

    class Meta:
        model = PurchaseOrder
        fields = ['number', 'supplier', 'expected_delivery', 'status', 'note']
        widgets = {
            'number': forms.TextInput(attrs={'readonly': 'readonly'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        self._request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        instance = kwargs.get('instance')
        
        # Obtener tasa de cambio
        # ✅ Obtener IVA de la empresa
        from django_erp.configuration.models import Company
        company = Company.get_active()
        tax_rate = Decimal(str(company.tax_rate)) if company else Decimal('16.00')
        rate = ExchangeRate.get_today_rate('USD', 'BS')
        if rate:
            self.initial['rate_display'] = f"1 USD = Bs. {rate:.2f}"
        else:
            self.initial['rate_display'] = "No hay tasa configurada"
        
        # Si es una orden existente, calcular totales
        if instance and instance.pk:
            subtotal = sum(line.subtotal for line in instance.lines.all())
            tax = subtotal * (tax_rate / Decimal('100'))
            total = subtotal + tax
            
            self.initial['subtotal_display'] = subtotal
            self.initial['tax_display'] = tax
            self.initial['total_display'] = total
            
            if rate:
                self.initial['subtotal_bs_display'] = f"{(subtotal * rate):.2f}"
                self.initial['tax_bs_display'] = f"{(tax * rate):.2f}"
                self.initial['total_bs_display'] = f"{(total * rate):.2f}"
        else:
            self.initial['subtotal_display'] = "0.00"
            self.initial['tax_display'] = "0.00"
            self.initial['total_display'] = "0.00"
            self.initial['subtotal_bs_display'] = "0.00"
            self.initial['tax_bs_display'] = "0.00"
            self.initial['total_bs_display'] = "0.00"
            
            # Autollenar datos de la empresa
            company = Company.get_active()
            if company:
                self.initial['tax_rate'] = company.tax_rate
                self.initial['tax_rate_display'] = f"{company.tax_rate}%"
            
            # Generar número automático
            from datetime import datetime
            last_order = PurchaseOrder.objects.order_by('-id').first()
            if last_order and last_order.number:
                try:
                    last_num = int(last_order.number.split('-')[-1])
                    next_num = last_num + 1
                except (ValueError, IndexError):
                    next_num = 1
            else:
                next_num = 1
            
            self.initial['number'] = f"COMPRA-{datetime.now().strftime('%Y%m%d')}-{next_num:04d}"
            self.fields['number'].disabled = True
            self.initial['status'] = 'DRAFT'
        
        # Configurar opciones de estado
        if instance and instance.pk:
            if instance.status == 'DRAFT':
                self.fields['status'].choices = [
                    ('DRAFT', 'Borrador'),
                    ('ORDERED', 'Ordenada'),
                ]
            elif instance.status == 'ORDERED':
                self.fields['status'].choices = [
                    ('ORDERED', 'Ordenada'),
                    ('RECEIVED', 'Recibida'),
                    ('CANCELLED', 'Cancelada'),
                ]
            elif instance.status == 'RECEIVED':
                self.fields['status'].choices = [
                    ('RECEIVED', 'Recibida'),
                ]
            elif instance.status == 'CANCELLED':
                self.fields['status'].choices = [
                    ('CANCELLED', 'Cancelada'),
                ]
        else:
            # Para nuevas órdenes
            self.fields['status'].choices = [
                ('DRAFT', 'Borrador'),
                ('ORDERED', 'Ordenada'),
            ]


@admin.action(description='✅ Confirmar órdenes seleccionadas')
def confirm_orders_action(modeladmin, request, queryset):
    """Acción para confirmar múltiples órdenes de compra"""
    from .services import PurchaseService
    
    for order in queryset:
        try:
            if order.status != 'DRAFT':
                modeladmin.message_user(
                    request, 
                    f'La orden {order.number} no está en borrador.', 
                    messages.WARNING
                )
                continue
            
            PurchaseService.confirm_order(order, request.user)
            modeladmin.message_user(
                request, 
                f'✅ Orden {order.number} confirmada exitosamente', 
                messages.SUCCESS
            )
        except Exception as e:
            modeladmin.message_user(
                request, 
                f'❌ Error con {order.number}: {str(e)}', 
                messages.ERROR
            )


@admin.action(description='📦 Recibir órdenes seleccionadas')
def receive_orders_action(modeladmin, request, queryset):
    """Acción para recibir múltiples órdenes de compra"""
    from .services import PurchaseService
    
    for order in queryset:
        try:
            if order.status != 'ORDERED':
                modeladmin.message_user(
                    request, 
                    f'La orden {order.number} no está en estado "Ordenada".', 
                    messages.WARNING
                )
                continue
            
            PurchaseService.receive_order(order, request.user)
            modeladmin.message_user(
                request, 
                f'✅ Orden {order.number} recibida exitosamente. '
                f'Se crearon movimientos de entrada en el almacén.', 
                messages.SUCCESS
            )
        except Exception as e:
            modeladmin.message_user(
                request, 
                f'❌ Error con {order.number}: {str(e)}', 
                messages.ERROR
            )

class PurchasePaymentInline(UnfoldTabularInline):
    """Inline de pagos para órdenes de compra"""
    model = PurchasePayment
    extra = 0
    fields = [
        'method', 
        'company_bank_account', 
        'currency', 
        'amount', 
        'amount_usd_display', 
        'reference', 
        'supplier_bank',
        'status',
        'payment_date'
    ]
    readonly_fields = ['payment_date', 'amount_usd_display']
    autocomplete_fields = ['method', 'company_bank_account', 'currency']
    
    # ✅ Ocultar el campo supplier (se asigna automáticamente)
    def get_formset(self, request, obj=None, **kwargs):
        formset = super().get_formset(request, obj, **kwargs)
        
        # ✅ Moneda por defecto: USD
        from django_erp.configuration.models import Currency
        try:
            usd = Currency.objects.get(code='USD')
            formset.form.base_fields['currency'].initial = usd.id
        except Currency.DoesNotExist:
            pass
        
        # ✅ Cuenta bancaria por defecto
        from django_erp.configuration.models import CompanyBankAccount
        default_account = CompanyBankAccount.get_default()
        if default_account:
            formset.form.base_fields['company_bank_account'].initial = default_account.id
        
        return formset
    
    @admin.display(description='Monto en USD')
    def amount_usd_display(self, obj):
        if obj and obj.amount_usd:
            return f"$ {obj.amount_usd:,.2f}"
        return "$ 0.00"
    
    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.select_related('method', 'company_bank_account', 'currency', 'supplier')
    
    # ✅ NUEVO: Guardar asignando el proveedor automáticamente
    def save_formset(self, request, form, formset, change):
        """Guardar pagos asignando el proveedor desde la orden"""
        instances = formset.save(commit=False)
        
        # ✅ Obtener la orden
        purchase_order = form.instance
        
        for obj in formset.deleted_objects:
            obj.delete()
        
        for obj in instances:
            # ✅ Asignar proveedor desde la orden
            obj.supplier = purchase_order.supplier
            obj.save()
        
        formset.save_m2m()



class PurchaseInvoiceInline(UnfoldTabularInline):
    """Inline de facturas de compra en la orden"""
    model = PurchaseInvoice
    extra = 0
    fields = ['number', 'date_issued', 'total', 'status']
    readonly_fields = ['number', 'date_issued', 'total', 'status']
    can_delete = False
    
    def has_add_permission(self, request, obj=None):
        return False



@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(UnfoldModelAdmin):
    form = PurchaseOrderForm
    
    list_display = [
        'number', 
        'supplier', 
        'date', 
        'expected_delivery',
        'subtotal', 
        'tax', 
        'total', 
        'status', 
        'created_at'
    ]
    list_filter = ['status', 'date']
    search_fields = ['number', 'supplier__name']
    
    inlines = [PurchaseLineInline, PurchasePaymentInline, PurchaseInvoiceInline]
    actions = [confirm_orders_action, receive_orders_action]
    autocomplete_fields = ['supplier']
    
    fieldsets = (
        ('Información de la Orden', {
            'fields': ('number', 'supplier', 'expected_delivery', 'status')
        }),
        ('Totales en Tiempo Real', {
            'fields': (
                ('subtotal_display', 'subtotal_bs_display'),
                ('tax_display', 'tax_bs_display'),
                ('total_display', 'total_bs_display'),
                'rate_display',
            ),
            'classes': ('tab', 'wide'),
            'description': 'Los totales se actualizan automáticamente al modificar las líneas'
        }),
        ('Información Adicional', {
            'fields': ('note',),
            'classes': ('tab',),
        }),
    )
    
    readonly_fields = ['user', 'date', 'created_at', 'updated_at']
    
    class Media:
        js = ('admin/js/purchase_order_admin.js', 'admin/js/purchase_payment_admin.js')

    def get_form(self, request, obj=None, **kwargs):
        """Pasar el request al formulario"""
        form = super().get_form(request, obj, **kwargs)
        form._request = request
        return form
    
    def save_model(self, request, obj, form, change):
        """Guardar la orden y procesar cambios de estado"""
        from .services import PurchaseService, PurchaseInvoiceService
        
        # ✅ Obtener el estado anterior ANTES de guardar
        old_status = None
        if change and obj.pk:
            try:
                old_status = PurchaseOrder.objects.get(pk=obj.pk).status
            except PurchaseOrder.DoesNotExist:
                pass
        
        # ✅ Obtener el nuevo estado del formulario
        new_status = form.cleaned_data.get('status')
        
        print(f"🔴 ===== SAVE_MODEL INICIADO =====")
        print(f"   Orden: {obj.number}")
        print(f"   Change: {change}")
        print(f"   Estado anterior: {old_status}")
        print(f"   Nuevo estado: {new_status}")
        
        # ✅ Asegurar que tax_rate se establezca desde la empresa si es nueva
        if not change and not obj.tax_rate:
            company = Company.get_active()
            if company:
                obj.tax_rate = company.tax_rate
            else:
                obj.tax_rate = Decimal('16.00')
        
        if not obj.user:
            obj.user = request.user
        
        # ✅ Guardar la orden
        super().save_model(request, obj, form, change)
        
        # ✅ Recalcular totales después de guardar
        if obj.pk:
            obj.calculate_totals()
            obj.save(update_fields=['subtotal', 'tax', 'total'])
        
        # ✅ Procesar cambio de estado (si cambió)
        if old_status != new_status:
            print(f"   🔄 El estado cambió de {old_status} a {new_status}")
            
            try:
                if new_status == 'ORDERED':
                    print("   ✅ EJECUTANDO: Confirmando orden...")
                    result = PurchaseService.confirm_order(obj, request.user)
                    print(f"   ✅ Resultado: {result}")
                    self.message_user(
                        request, 
                        f'✅ Orden {obj.number} confirmada exitosamente', 
                        messages.SUCCESS
                    )
                
                elif new_status == 'RECEIVED':
                    print("   📦 EJECUTANDO: Recibiendo orden...")
                    
                    # ✅ PASO 1: Recibir la orden (esto cambia el estado a RECEIVED)
                    result = PurchaseService.receive_order(obj, request.user)
                    print(f"   ✅ Resultado: {result}")
                    
                    # ✅ PASO 2: Recargar la orden desde la BD para tener el estado actualizado
                    obj.refresh_from_db()
                    
                    # ✅ PASO 3: Generar factura (ahora la orden ya está en estado RECEIVED)
                    print("   📄 Generando factura de compra...")
                    try:
                        # ✅ Verificar que no tenga factura aún
                        if not obj.invoiced:
                            invoice = PurchaseInvoiceService.create_invoice_from_purchase_order(
                                obj.id, 
                                request.user
                            )
                            print(f"   ✅ Factura {invoice.number} generada")
                            self.message_user(
                                request, 
                                f'✅ Orden {obj.number} recibida. Factura de compra {invoice.number} generada automáticamente.', 
                                messages.SUCCESS
                            )
                        else:
                            print(f"   ℹ️ La orden ya tiene factura")
                            self.message_user(
                                request, 
                                f'✅ Orden {obj.number} recibida (ya tenía factura).', 
                                messages.SUCCESS
                            )
                    except Exception as e:
                        print(f"   ❌ Error generando factura: {e}")
                        import traceback
                        traceback.print_exc()
                        self.message_user(
                            request, 
                            f'⚠️ Orden recibida pero error al generar factura: {str(e)}', 
                            messages.WARNING
                        )
                
                elif new_status == 'CANCELLED':
                    print("   ❌ EJECUTANDO: Cancelando orden...")
                    result = PurchaseService.cancel_order(obj, request.user)
                    print(f"   ✅ Resultado: {result}")
                    self.message_user(
                        request, 
                        f'✅ Orden {obj.number} cancelada exitosamente', 
                        messages.SUCCESS
                    )
            
            except Exception as e:
                print(f"   ❌ Error: {str(e)}")
                print(traceback.format_exc())
                
                self.message_user(
                    request, 
                    f'❌ Error: {str(e)}', 
                    messages.ERROR
                )
                # ✅ Revertir al estado anterior
                obj.status = old_status
                obj.save(update_fields=['status'])
        else:
            print("   ℹ️ El estado no cambió")
        
        print("🔴 ===== FIN SAVE_MODEL =====")
    
    def save_formset(self, request, form, formset, change):
        """Guardar líneas y recalcular totales"""
        print("🔴 ===== SAVE_FORMSET INICIADO =====")
        
        # ✅ 1. Guardar las líneas
        super().save_formset(request, form, formset, change)
        
        # ✅ 2. Obtener la instancia actualizada
        obj = form.instance
        
        # ✅ 3. Recalcular totales
        obj.calculate_totals()
        obj.save(update_fields=['subtotal', 'tax', 'total', 'updated_at'])
        
        print(f"   ✅ Total calculado: {obj.total}")
        print("🔴 ===== FIN SAVE_FORMSET =====")


class PurchaseInvoiceLineInline(UnfoldTabularInline):
    """Inline de líneas de factura de compra"""
    model = PurchaseInvoiceLine
    extra = 0
    fields = ['product', 'quantity', 'unit_price', 'subtotal']
    readonly_fields = ['subtotal']
    autocomplete_fields = ['product']
    
    def get_formset(self, request, obj=None, **kwargs):
        formset = super().get_formset(request, obj, **kwargs)
        from django_erp.warehouse.models import Product
        formset.form.base_fields['product'].queryset = Product.objects.filter(is_active=True)
        return formset


@admin.register(PurchaseInvoice)
class PurchaseInvoiceAdmin(UnfoldModelAdmin):
    """Admin de facturas de compra"""
    
    list_display = [
        'number', 
        'supplier', 
        'date_issued', 
        'total', 
        'status', 
        'created_at'
    ]
    list_filter = ['status', 'date_issued']
    search_fields = ['number', 'supplier__name', 'supplier_rif']
    
    inlines = [PurchaseInvoiceLineInline]
    autocomplete_fields = ['supplier', 'purchase_order']
    
    fieldsets = (
        ('Información', {
            'fields': ('number', 'purchase_order', 'supplier', 'status')
        }),
        ('Datos del Proveedor', {
            'fields': ('supplier_name', 'supplier_rif', 'supplier_address')
        }),
        ('Fechas', {
            'fields': ('date_issued', 'date_due')
        }),
        ('Totales', {
            'fields': ('subtotal', 'tax', 'total')
        }),
        ('Información Adicional', {
            'fields': ('note',)
        }),
    )
    
    readonly_fields = ['date_issued', 'subtotal', 'tax', 'total', 'user', 'created_at', 'updated_at']
    
    class Media:
        js = ('admin/js/purchase_invoice_admin.js',)
    
    def save_model(self, request, obj, form, change):
        if not obj.user:
            obj.user = request.user
        super().save_model(request, obj, form, change)
        obj.calculate_totals()
        obj.save(update_fields=['subtotal', 'tax', 'total'])