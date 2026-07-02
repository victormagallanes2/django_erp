# invoicing/admin.py
from django.contrib import admin
from django import forms
from django.utils.html import format_html
from django.urls import reverse
from unfold.admin import ModelAdmin as UnfoldModelAdmin
from unfold.admin import TabularInline as UnfoldTabularInline
from .models import Invoice, InvoiceLine


class InvoiceLineInline(UnfoldTabularInline):
    model = InvoiceLine
    extra = 1
    fields = ['product', 'description', 'quantity', 'unit_price', 'subtotal']
    readonly_fields = ['subtotal']


class InvoiceForm(forms.ModelForm):
    class Meta:
        model = Invoice
        fields = '__all__'
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        instance = kwargs.get('instance')
        
        # ✅ Cliente: mostrar nombre y RIF, no editable
        if instance and instance.customer:
            self.fields['customer'].disabled = True
            self.fields['customer'].help_text = f"{instance.customer.name} - {instance.customer.tax_id}"
        else:
            self.fields['customer'].disabled = True
        
        # ✅ Orden de Venta: mostrar número, no editable
        if instance and instance.sale_order:
            self.fields['sale_order'].disabled = True
            self.fields['sale_order'].help_text = f"{instance.sale_order.number}"
        else:
            self.fields['sale_order'].disabled = True
        
        # ✅ Número Interno: no editable
        self.fields['number'].disabled = True
        
        if not instance or not instance.pk:
            from datetime import datetime
            last_invoice = Invoice.objects.order_by('-id').first()
            if last_invoice and last_invoice.number:
                try:
                    last_num = int(last_invoice.number.split('-')[-1])
                    next_num = last_num + 1
                except (ValueError, IndexError):
                    next_num = 1
            else:
                next_num = 1
            
            self.initial['number'] = f"FAC-{datetime.now().strftime('%Y%m')}-{next_num:04d}"
            self.initial['status'] = 'DRAFT'
            self.fields['status'].choices = [
                ('DRAFT', 'Borrador'),
            ]
        else:
            if instance.status == 'DRAFT':
                self.fields['status'].choices = [
                    ('DRAFT', 'Borrador'),
                    ('ISSUED', 'Emitida'),
                ]
            elif instance.status == 'ISSUED':
                self.fields['status'].choices = [
                    ('ISSUED', 'Emitida'),
                    ('PAID', 'Pagada'),
                    ('CANCELLED', 'Anulada'),
                ]
            elif instance.status == 'PAID':
                self.fields['status'].choices = [
                    ('PAID', 'Pagada'),
                ]
            elif instance.status == 'CANCELLED':
                self.fields['status'].choices = [
                    ('CANCELLED', 'Anulada'),
                ]


@admin.register(Invoice)
class InvoiceAdmin(UnfoldModelAdmin):
    form = InvoiceForm
    
    list_display = ['number', 'customer_display', 'sale_order_display', 'date', 'total', 'status', 'created_at']
    list_filter = ['status', 'date']
    search_fields = ['number', 'customer__name', 'sale_order__number']
    
    inlines = [InvoiceLineInline]
    
    fieldsets = (
        ('Información', {
            'fields': ('number', 'customer', 'sale_order', 'status')
        }),
        ('Datos Fiscales', {
            'fields': ('issuer_rif', 'issuer_name', 'issuer_address'),
            'classes': ('tab',),
        }),
        ('Datos del Cliente', {
            'fields': ('customer_rif', 'customer_address'),
            'classes': ('tab',),
        }),
        ('Totales', {
            'fields': ('subtotal', 'tax_rate', 'tax', 'total'),
            'classes': ('tab',),
        }),
        ('Información Adicional', {
            'fields': ('note',),
            'classes': ('tab',),
        }),
    )
    
    readonly_fields = ['date', 'subtotal', 'tax', 'total', 'user', 'created_at', 'updated_at']
    
    # ✅ Ocultar raw_id_fields para que no se vea el botón de lupa
    # raw_id_fields = []  # Eliminado
    
    @admin.display(description='Cliente')
    def customer_display(self, obj):
        """Mostrar cliente con RIF en el listado"""
        if obj.customer:
            return f"{obj.customer.name} ({obj.customer.tax_id})"
        return "-"
    
    @admin.display(description='Orden de Venta')
    def sale_order_display(self, obj):
        """Mostrar solo el número de orden en el listado"""
        if obj.sale_order:
            url = reverse('admin:sales_saleorder_change', args=[obj.sale_order.id])
            return format_html(
                '<a href="{}">{}</a>',
                url,
                obj.sale_order.number
            )
        return "-"
    
# invoicing/admin.py - En InvoiceAdmin

    def save_model(self, request, obj, form, change):
        from .services import InvoiceService
        
        if not obj.user:
            obj.user = request.user
        
        # Guardar estado anterior
        if change and obj.pk:
            old_obj = Invoice.objects.get(pk=obj.pk)
            old_status = old_obj.status
        else:
            old_status = None
        
        new_status = form.cleaned_data.get('status')
        print(f"🔍 Invoicing Admin: old_status={old_status}, new_status={new_status}")
        
        if old_status != new_status:
            if new_status == 'ISSUED':
                print("🔔 Invoicing Admin: Emitiendo factura...")
                # ✅ Cambiar estado en el objeto ANTES
                obj.status = 'ISSUED'
                InvoiceService.issue_invoice(obj, request.user)
            elif new_status == 'PAID':
                print("🔔 Invoicing Admin: Pagando factura...")
                obj.status = 'PAID'
                InvoiceService.pay_invoice(obj, request.user)
            elif new_status == 'CANCELLED':
                print("🔔 Invoicing Admin: Anulando factura...")
                obj.status = 'CANCELLED'
                InvoiceService.cancel_invoice(obj, request.user)
        
        # Guardar en base de datos
        super().save_model(request, obj, form, change)
    
    def save_formset(self, request, form, formset, change):
        super().save_formset(request, form, formset, change)
        form.instance.calculate_totals()
        form.instance.save()