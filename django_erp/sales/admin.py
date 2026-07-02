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
    
    # ✅ Botón para generar factura
    def get_invoice_button(self, obj):
        """Mostrar botón solo si Invoicing está instalado"""
        if not apps.is_installed('django_erp.invoicing'):
            return ''
        
        if obj and obj.status == 'CONFIRMED' and not hasattr(obj, 'invoice'):
            url = reverse('invoicing:generate_invoice_from_order', args=[obj.id])
            return format_html(
                '<div style="margin: 15px 0;">'
                '<a href="{}" class="button" style="background: #28a745; color: white; padding: 8px 16px; border-radius: 4px; text-decoration: none; display: inline-block; font-weight: bold;">'
                '📄 Generar Factura'
                '</a>'
                '</div>',
                url
            )
        return ''
    
    def change_view(self, request, object_id, form_url='', extra_context=None):
        extra_context = extra_context or {}
        from .models import SaleOrder
        try:
            obj = SaleOrder.objects.get(id=object_id)
            extra_context['invoice_button'] = self.get_invoice_button(obj)
        except SaleOrder.DoesNotExist:
            pass
        return super().change_view(request, object_id, form_url, extra_context)
    
    # ✅ save_model modificado
    def save_model(self, request, obj, form, change):
        from .services import SaleService
        
        if not obj.user:
            obj.user = request.user
        
        # Guardar estado anterior
        if change and obj.pk:
            old_obj = SaleOrder.objects.get(pk=obj.pk)
            old_status = old_obj.status
        else:
            old_status = None
        
        new_status = form.cleaned_data.get('status')
        print(f"🔍 Sales Admin: old_status={old_status}, new_status={new_status}")
        
        # ✅ Si es nueva orden (sin pk), guardar primero para tener ID
        if not obj.pk:
            print("📝 Es una nueva orden, guardando primero...")
            super().save_model(request, obj, form, change)
            return
        
        if old_status != new_status:
            if new_status == 'CONFIRMED':
                print("🔔 Sales Admin: Confirmando orden...")
                
                # ✅ Cambiar estado en el objeto
                obj.status = 'CONFIRMED'
                
                # ✅ GUARDAR PRIMERO
                super().save_model(request, obj, form, change)
                
                # ✅ Ejecutar confirmación (crea movimientos de stock)
                SaleService.confirm_order(obj, request.user)
                
                # ✅ Generar factura
                if apps.is_installed('django_erp.invoicing'):
                    print("📄 Sales Admin: Invoicing instalado, generando factura...")
                    try:
                        from django_erp.invoicing.services import InvoiceService
                        invoice = InvoiceService.create_invoice_from_sale_order(obj.id, request.user)
                        print(f"✅ Factura {invoice.number} generada")
                    except Exception as e:
                        print(f"❌ Error al generar factura: {e}")
                else:
                    print("⚠️ Invoicing no instalado")
                    
            elif new_status == 'CANCELLED':
                print("🔔 Sales Admin: Cancelando orden...")
                obj.status = 'CANCELLED'
                super().save_model(request, obj, form, change)
                SaleService.cancel_order(obj, request.user, old_status)
            elif new_status == 'DELIVERED':
                print("🔔 Sales Admin: Entregando orden...")
                obj.status = 'DELIVERED'
                super().save_model(request, obj, form, change)
                SaleService.deliver_order(obj, request.user)
        else:
            # Si el estado no cambió, guardar normalmente
            super().save_model(request, obj, form, change)
    
    def save_formset(self, request, form, formset, change):
        super().save_formset(request, form, formset, change)
        form.instance.calculate_totals()
        form.instance.save()