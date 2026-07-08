# sales/admin.py
from django.contrib import admin
from django import forms
from django.utils.html import format_html
from django.urls import reverse
from django.apps import apps
from unfold.admin import ModelAdmin as UnfoldModelAdmin
from unfold.admin import TabularInline as UnfoldTabularInline
from .models import Customer, SaleOrder, SaleLine


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
    extra = 1
    fields = ['product', 'location', 'quantity', 'unit_price', 'subtotal']
    readonly_fields = ['subtotal']
    autocomplete_fields = ['product']
    
    def get_formset(self, request, obj=None, **kwargs):
        formset = super().get_formset(request, obj, **kwargs)
        from django_erp.warehouse.models import Product, Location
        formset.form.base_fields['product'].queryset = Product.objects.filter(is_active=True)
        formset.form.base_fields['location'].queryset = Location.objects.filter(is_active=True)
        return formset


class SaleOrderForm(forms.ModelForm):
    """Formulario personalizado con totales calculados en tiempo real"""
    
    # ✅ Crear campos adicionales para mostrar totales (no vinculados al modelo)
    subtotal_display = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        required=False,
        disabled=True,
        label="Subtotal",
        initial=0.00
    )
    tax_display = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        required=False,
        disabled=True,
        label="IVA (19%)",
        initial=0.00
    )
    total_display = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        required=False,
        disabled=True,
        label="Total",
        initial=0.00
    )
    
    class Meta:
        model = SaleOrder
        fields = ['number', 'customer', 'status', 'note']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        instance = kwargs.get('instance')
        
        # ✅ Inicializar campos de totales con valores del modelo si existen
        if instance and instance.pk:
            self.initial['subtotal_display'] = instance.subtotal
            self.initial['tax_display'] = instance.tax
            self.initial['total_display'] = instance.total
        
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
            'fields': ('subtotal_display', 'tax_display', 'total_display'),
            'classes': ('tab',),
            'description': 'Los totales se actualizan automáticamente al modificar las líneas'
        }),
        ('Información Adicional', {
            'fields': ('note',),
            'classes': ('tab',),
        }),
    )
    
    readonly_fields = ['user', 'date', 'created_at', 'updated_at']
    
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