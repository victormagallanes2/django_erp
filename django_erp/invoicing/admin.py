# invoicing/admin.py
from django.contrib import admin
from django import forms
from django.utils.html import format_html
from django.urls import reverse
from django.apps import apps
from unfold.admin import ModelAdmin as UnfoldModelAdmin
from unfold.admin import TabularInline as UnfoldTabularInline
from .models import Invoice, InvoiceLine
from django_erp.configuration.models import Company


class InvoiceLineInline(UnfoldTabularInline):
    model = InvoiceLine
    extra = 1
    fields = ['product_code', 'product_name', 'description', 'quantity', 'unit_price', 'subtotal']
    readonly_fields = ['subtotal']


class InvoiceForm(forms.ModelForm):
    class Meta:
        model = Invoice
        fields = '__all__'
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        instance = kwargs.get('instance')
        
        # Autollenar datos de la empresa si es nueva factura
        if not instance or not instance.pk:
            company = Company.get_active()
            if company:
                self.initial['company'] = company.id
                self.initial['issuer_rif'] = company.rif
                self.initial['issuer_name'] = company.name
                self.initial['issuer_address'] = company.address
                self.initial['tax_rate'] = company.tax_rate
        
        # ✅ Ocultar el campo company
        if 'company' in self.fields:
            self.fields['company'].widget = forms.HiddenInput()
            self.fields['company'].required = True
        
        # Número interno: no editable
        if 'number' in self.fields:
            self.fields['number'].disabled = True
        
        # Estado según el estado actual
        if instance and instance.pk:
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
        else:
            # Nueva factura
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


@admin.register(Invoice)
class InvoiceAdmin(UnfoldModelAdmin):
    form = InvoiceForm
    
    list_display = ['number', 'customer_name', 'customer_rif', 'issuer_rif', 'date', 'total', 'status', 'created_at']
    list_filter = ['status', 'date']
    search_fields = ['number', 'customer_name', 'customer_rif', 'concept']
    
    inlines = [InvoiceLineInline]
    
    fieldsets = (
        ('Información', {
            'fields': ('number', 'customer_name', 'customer_rif', 'customer_address', 'sale_order_number', 'concept', 'status')
        }),
        ('Datos Fiscales del Emisor', {
            'fields': ('issuer_rif', 'issuer_name', 'issuer_address'),
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
    
    def save_model(self, request, obj, form, change):
        from .services import InvoiceService
        
        # ✅ Asegurar que company se asigne antes de guardar
        if not obj.company_id:
            company = Company.get_active()
            if company:
                obj.company = company
        
        if not obj.user:
            obj.user = request.user
        
        if change and obj.pk:
            old_obj = Invoice.objects.get(pk=obj.pk)
            old_status = old_obj.status
        else:
            old_status = None
        
        new_status = form.cleaned_data.get('status')
        
        if old_status != new_status:
            if new_status == 'ISSUED':
                obj.status = 'ISSUED'
                InvoiceService.issue_invoice(obj, request.user)
            elif new_status == 'PAID':
                obj.status = 'PAID'
                InvoiceService.pay_invoice(obj, request.user)
            elif new_status == 'CANCELLED':
                obj.status = 'CANCELLED'
                InvoiceService.cancel_invoice(obj, request.user)
        
        super().save_model(request, obj, form, change)
    
    def save_formset(self, request, form, formset, change):
        super().save_formset(request, form, formset, change)
        form.instance.calculate_totals()
        form.instance.save()