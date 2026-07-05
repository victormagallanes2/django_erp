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
    search_fields = ['name', 'tax_id', 'email']
    
    fieldsets = (
        ('Información', {'fields': ('name', 'tax_id', 'email', 'phone', 'address')}),
        ('Estado', {'fields': ('is_active',)}),
    )
    readonly_fields = ['created_at', 'updated_at']


class SaleLineInline(UnfoldTabularInline):
    model = SaleLine
    extra = 1
    fields = ['product', 'location', 'product_name', 'location_code', 'description', 'quantity', 'unit_price', 'subtotal']
    readonly_fields = ['subtotal']
    autocomplete_fields = ['product', 'location']


class SaleOrderForm(forms.ModelForm):
    class Meta:
        model = SaleOrder
        fields = '__all__'
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        instance = kwargs.get('instance')
        
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
    
    fieldsets = (
        ('Información', {
            'fields': ('number', 'customer', 'status')
        }),
        ('Totales', {
            'fields': ('subtotal', 'tax', 'total'),
            'classes': ('tab',),
        }),
        ('Información Adicional', {
            'fields': ('note',),
            'classes': ('tab',),
        }),
    )
    
    readonly_fields = ['subtotal', 'tax', 'total', 'user', 'date', 'created_at', 'updated_at']
    
    def save_model(self, request, obj, form, change):
        from .services import SaleService
        
        if not obj.user:
            obj.user = request.user
        
        # Guardar estado anterior (ANTES de modificar el objeto)
        if change and obj.pk:
            old_obj = SaleOrder.objects.get(pk=obj.pk)
            old_status = old_obj.status
        else:
            old_status = None
        
        new_status = form.cleaned_data.get('status')
        
        if old_status != new_status:
            if new_status == 'CONFIRMED':
                obj.status = 'CONFIRMED'
                SaleService.confirm_order(obj, request.user)
            elif new_status == 'CANCELLED':
                # ✅ Pasar old_status para saber si estaba confirmada
                SaleService.cancel_order(obj, request.user, old_status)
                obj.status = 'CANCELLED'
            elif new_status == 'DELIVERED':
                obj.status = 'DELIVERED'
                SaleService.deliver_order(obj, request.user)
        
        # Guardar en base de datos
        super().save_model(request, obj, form, change)