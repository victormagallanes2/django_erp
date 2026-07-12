# sales/admin.py
from django.contrib import admin
from django import forms
from django.utils.html import format_html
from django.urls import reverse
from django.apps import apps
from unfold.admin import ModelAdmin as UnfoldModelAdmin
from unfold.admin import TabularInline as UnfoldTabularInline
from .models import Customer, SaleOrder, SaleLine
from .models import CashRegister, CashTransaction
from decimal import Decimal, ROUND_HALF_UP


@admin.register(Customer)
class CustomerAdmin(UnfoldModelAdmin):
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


class SaleLineInline(UnfoldTabularInline):
    model = SaleLine
    extra = 0
    fields = ['product', 'location', 'quantity', 'unit_price', 'subtotal']
    readonly_fields = ['subtotal']
    autocomplete_fields = ['product']
    
    def get_formset(self, request, obj=None, **kwargs):
        formset = super().get_formset(request, obj, **kwargs)
        from django_erp.warehouse.models import Product, Location
        formset.form.base_fields['product'].queryset = Product.objects.filter(is_active=True)
        formset.form.base_fields['location'].queryset = Location.objects.filter(is_active=True)
        formset.form.base_fields['unit_price'].initial = 0
        formset.form.base_fields['quantity'].initial = 1
        return formset
    
    @admin.display(description='Precio en Bs.')
    def price_bs_display(self, obj):
        """Mostrar precio en Bolívares"""
        if obj.unit_price and obj.unit_price > 0:
            try:
                from django_erp.configuration.models import ExchangeRate
                rate = ExchangeRate.get_today_rate('USD', 'BS')
                if rate:
                    price_bs = obj.unit_price * rate
                    return f"Bs. {price_bs:.2f}"
                else:
                    return "Sin tasa"
            except Exception as e:
                return f"Error: {str(e)}"
        return "-"


class SaleOrderForm(forms.ModelForm):
    subtotal_display = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        required=False,
        disabled=True,
        label="Subtotal (USD)",
        initial=0.00
    )
    
    subtotal_bs_display = forms.DecimalField(
        max_digits=20,
        decimal_places=2,
        required=False,
        disabled=True,
        label="Subtotal (Bs.)",
        initial=0.00
    )
    
    tax_display = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        required=False,
        disabled=True,
        label="IVA (USD)",
        initial=0.00
    )
    
    tax_bs_display = forms.DecimalField(
        max_digits=20,
        decimal_places=2,
        required=False,
        disabled=True,
        label="IVA (Bs.)",
        initial=0.00
    )
    
    total_display = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        required=False,
        disabled=True,
        label="Total (USD)",
        initial=0.00
    )
    
    total_bs_display = forms.DecimalField(
        max_digits=20,
        decimal_places=2,
        required=False,
        disabled=True,
        label="Total (Bs.)",
        initial=0.00,
        help_text="Convertido según tasa del día"
    )
    
    rate_display = forms.CharField(
        required=False,
        disabled=True,
        label="Tasa del día",
        initial="1 USD = Bs. 0.00"
    )
    
    class Meta:
        model = SaleOrder
        fields = ['number', 'customer', 'status', 'note']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        instance = kwargs.get('instance')
        
        from django_erp.configuration.models import ExchangeRate
        rate = ExchangeRate.get_today_rate('USD', 'BS')
        if rate:
            self.initial['rate_display'] = f"1 USD = Bs. {rate:.2f}"
        else:
            self.initial['rate_display'] = "No hay tasa configurada"
        
        if instance and instance.total:
            if rate:
                # ✅ Convertir a Decimal con 2 decimales usando ROUND_HALF_UP
                self.initial['subtotal_bs_display'] = Decimal(str(instance.subtotal * rate)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                self.initial['tax_bs_display'] = Decimal(str(instance.tax * rate)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                self.initial['total_bs_display'] = Decimal(str(instance.total * rate)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            else:
                self.initial['total_bs_display'] = instance.total
        else:
            self.initial['subtotal_bs_display'] = Decimal('0.00')
            self.initial['tax_bs_display'] = Decimal('0.00')
            self.initial['total_bs_display'] = Decimal('0.00')
        
        if not instance or not instance.pk:
            from datetime import datetime
            last_order = SaleOrder.objects.order_by('-id').first()
            if last_order and last_order.number:
                try:
                    last_num = int(last_order.number.split('-')[-1])
                    next_num = last_num + 1
                except (ValueError, IndexError):
                    next_num = 1
            else:
                next_num = 1
            
            self.initial['number'] = f"VENTA-{datetime.now().strftime('%Y%m%d')}-{next_num:04d}"
            self.fields['number'].disabled = True
            self.initial['status'] = 'DRAFT'
            self.fields['status'].choices = [
                ('DRAFT', 'Borrador'),
            ]
        else:
            if instance.status == 'DRAFT':
                self.fields['status'].choices = [
                    ('DRAFT', 'Borrador'),
                    ('CONFIRMED', 'Confirmada'),
                ]
            elif instance.status == 'CONFIRMED':
                self.fields['status'].choices = [
                    ('CONFIRMED', 'Confirmada'),
                    ('DELIVERED', 'Entregada'),
                    ('CANCELLED', 'Cancelada'),
                ]
            elif instance.status == 'DELIVERED':
                self.fields['status'].choices = [
                    ('DELIVERED', 'Entregada'),
                ]
            elif instance.status == 'CANCELLED':
                self.fields['status'].choices = [
                    ('CANCELLED', 'Cancelada'),
                ]


@admin.register(SaleOrder)
class SaleOrderAdmin(UnfoldModelAdmin):
    form = SaleOrderForm
    
    list_display = ['number', 'customer', 'date', 'total', 'status', 'created_at']
    list_filter = ['status', 'date']
    search_fields = ['number', 'customer__name']
    
    inlines = [SaleLineInline]
    
    autocomplete_fields = ['customer']
    
    # ✅ fieldsets con campos de totales calculados
    fieldsets = (
    ('Información de la Orden', {
        'fields': ('number', 'customer', 'status')
    }),
    ('Totales en Tiempo Real', {
        'fields': (
            ('subtotal_display', 'subtotal_bs_display'),  # ← Ahora existen ambos
            ('tax_display', 'tax_bs_display'),            # ← Ahora existen ambos
            ('total_display', 'total_bs_display'),        # ← Ya existe
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

    def has_add_permission(self, request):
        return request.user.has_perm('sales.add_saleorder')
    
    def has_change_permission(self, request, obj=None):
        return request.user.has_perm('sales.change_saleorder')
    
    def has_delete_permission(self, request, obj=None):
        return request.user.has_perm('sales.delete_saleorder')
    
    def has_view_permission(self, request, obj=None):
        return request.user.has_perm('sales.view_saleorder')
    
    # ✅ Acciones solo si tiene permiso
    def get_actions(self, request):
        actions = super().get_actions(request)
        if not request.user.has_perm('sales.can_confirm_order'):
            actions.pop('confirm_order', None)
        if not request.user.has_perm('sales.can_cancel_order'):
            actions.pop('cancel_order', None)
        return actions
    
    class Media:
        js = ('admin/js/sale_order_admin.js',)
    
    def save_model(self, request, obj, form, change):
        from .services import SaleService
        
        if not obj.user:
            obj.user = request.user
        
        # ✅ Guardar los valores calculados en el modelo
        obj.subtotal = form.cleaned_data.get('subtotal_display', 0)
        obj.tax = form.cleaned_data.get('tax_display', 0)
        obj.total = form.cleaned_data.get('total_display', 0)
        
        if not obj.pk:
            super().save_model(request, obj, form, change)
            return
        
        if change and obj.pk:
            old_obj = SaleOrder.objects.get(pk=obj.pk)
            old_status = old_obj.status
        else:
            old_status = None
        
        new_status = form.cleaned_data.get('status')
        
        if old_status != new_status:
            if new_status == 'CONFIRMED':
                super().save_model(request, obj, form, change)
                obj.status = 'CONFIRMED'
                SaleService.confirm_order(obj, request.user)
            elif new_status == 'CANCELLED':
                SaleService.cancel_order(obj, request.user, old_status)
                obj.status = 'CANCELLED'
                super().save_model(request, obj, form, change)
            elif new_status == 'DELIVERED':
                obj.status = 'DELIVERED'
                SaleService.deliver_order(obj, request.user)
                super().save_model(request, obj, form, change)
        else:
            super().save_model(request, obj, form, change)
    
    def save_formset(self, request, form, formset, change):
        super().save_formset(request, form, formset, change)
        
        for line in form.instance.lines.all():
            if line.product and not line.location:
                from django_erp.inventory.models import Inventory
                inventory = Inventory.objects.filter(product=line.product).first()
                if inventory and inventory.location:
                    line.location = inventory.location
                    line.save()
        
        form.instance.calculate_totals()
        form.instance.save()


@admin.register(CashRegister)
class CashRegisterAdmin(UnfoldModelAdmin):
    list_display = [
        'number', 'user', 'date', 'status_badge', 
        'total_sales', 'expected_total', 'counted_total', 'difference'
    ]
    list_filter = ['status', 'date']
    search_fields = ['number', 'user__username']
    
    fieldsets = (
        ('Información', {
            'fields': ('number', 'user', 'status')
        }),
        ('Dinero', {
            'fields': ('initial_amount', 'total_sales', 'total_expenses', 
                       'total_withdrawals', 'expected_total')
        }),
        ('Cierre', {
            'fields': ('counted_total', 'breakdown', 'difference', 'note'),
            'classes': ('tab',),
        }),
        ('Fechas', {
            'fields': ('opened_at', 'closed_at'),
            'classes': ('tab',),
        }),
    )
    
    readonly_fields = [
        'opened_at', 'closed_at', 'total_sales', 
        'total_expenses', 'total_withdrawals', 'expected_total'
    ]
    
    # ✅ Generar número en get_form
    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        
        # ✅ Si es una nueva caja, generar número inicial
        if obj is None:
            from datetime import datetime
            date_str = datetime.now().strftime('%Y%m%d')
            last = CashRegister.objects.filter(
                number__startswith=f'CAJA-{date_str}'
            ).order_by('number').last()
            
            if last:
                try:
                    last_num = int(last.number.split('-')[-1])
                    next_num = last_num + 1
                except (ValueError, IndexError):
                    next_num = 1
            else:
                next_num = 1
            
            # ✅ Usar base_fields para establecer el valor inicial
            form.base_fields['number'].initial = f'CAJA-{date_str}-{next_num:04d}'
            form.base_fields['number'].disabled = True
        
        return form
    
    def save_model(self, request, obj, form, change):
        # ✅ Si no tiene número, generarlo antes de guardar
        if not obj.number:
            from datetime import datetime
            date_str = datetime.now().strftime('%Y%m%d')
            last = CashRegister.objects.filter(
                number__startswith=f'CAJA-{date_str}'
            ).order_by('number').last()
            
            if last:
                try:
                    last_num = int(last.number.split('-')[-1])
                    next_num = last_num + 1
                except (ValueError, IndexError):
                    next_num = 1
            else:
                next_num = 1
            
            obj.number = f'CAJA-{date_str}-{next_num:04d}'
        
        super().save_model(request, obj, form, change)
    
    @admin.display(description='Estado')
    def status_badge(self, obj):
        colors = {
            'OPEN': ('#28a745', '✅ Abierta'),
            'CLOSED': ('#17a2b8', '🔒 Cerrada'),
            'APPROVED': ('#28a745', '✅ Aprobada'),
            'CANCELLED': ('#dc3545', '❌ Cancelada'),
        }
        color, label = colors.get(obj.status, ('#6c757d', obj.status))
        return format_html(
            '<span style="background: {}; color: white; padding: 2px 10px; border-radius: 12px; font-size: 12px;">{}</span>',
            color,
            label
        )


@admin.register(CashTransaction)
class CashTransactionAdmin(UnfoldModelAdmin):
    list_display = ['register', 'type', 'amount', 'description', 'user', 'created_at']
    list_filter = ['type']
    search_fields = ['description', 'reference']
    readonly_fields = ['created_at']