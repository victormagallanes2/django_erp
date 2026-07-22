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
from django_erp.configuration.models import PaymentMethod
from django.utils.safestring import mark_safe


class InvoiceLineInline(UnfoldTabularInline):
    model = InvoiceLine
    extra = 0
    fields = ['product', 'quantity', 'unit_price', 'subtotal']  # ← Igual que Sales
    readonly_fields = ['subtotal']
    autocomplete_fields = ['product']  # ← Igual que Sales
    
    def get_formset(self, request, obj=None, **kwargs):
        formset = super().get_formset(request, obj, **kwargs)
        from django_erp.warehouse.models import Product
        formset.form.base_fields['product'].queryset = Product.objects.filter(is_active=True)
        formset.form.base_fields['unit_price'].initial = 0
        formset.form.base_fields['quantity'].initial = 1
        return formset
    
    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.select_related('product')


class InvoiceForm(forms.ModelForm):
    # ✅ Campos para totales en USD (como Sales)
    subtotal_display = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        required=False,
        disabled=True,
        label="Subtotal (USD)",
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
    
    total_display = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        required=False,
        disabled=True,
        label="Total (USD)",
        initial=0.00
    )
    
    # ✅ Campos para totales en Bs. (como Sales)
    subtotal_bs_display = forms.DecimalField(
        max_digits=20,
        decimal_places=2,
        required=False,
        disabled=True,
        label="Subtotal (Bs.)",
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
        model = Invoice
        fields = '__all__'
        widgets = {
            'product_code': forms.TextInput(attrs={'readonly': 'readonly'}),
            'product_name': forms.TextInput(attrs={'readonly': 'readonly'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        instance = kwargs.get('instance')
        if instance and instance.customer:
            self.initial['customer_name'] = instance.customer.name
            self.initial['customer_rif'] = instance.customer.tax_id
            self.initial['customer_address'] = instance.customer.address

        from django_erp.configuration.models import ExchangeRate
        rate = ExchangeRate.get_today_rate('USD', 'BS')
        if rate:
            self.initial['rate_display'] = f"1 USD = Bs. {rate:.2f}"
        else:
            self.initial['rate_display'] = "No hay tasa configurada"
        
        if instance and instance.pk:
            self.initial['subtotal_display'] = instance.subtotal
            self.initial['tax_display'] = instance.tax
            self.initial['total_display'] = instance.total
            
            if rate:
                self.initial['subtotal_bs_display'] = instance.subtotal * rate
                self.initial['tax_bs_display'] = instance.tax * rate
                self.initial['total_bs_display'] = instance.total * rate
        else:
            self.initial['subtotal_display'] = 0.00
            self.initial['tax_display'] = 0.00
            self.initial['total_display'] = 0.00
            self.initial['subtotal_bs_display'] = 0.00
            self.initial['tax_bs_display'] = 0.00
            self.initial['total_bs_display'] = 0.00
        
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
    
    list_display = ['number', 'customer_name', 'customer_rif', 'issuer_rif', 'date', 'total', 'status', 'created_at', 'paid_amount_display']
    list_filter = ['status', 'date']
    search_fields = ['number', 'customer__name', 'customer_rif', 'concept']
    
    inlines = [InvoiceLineInline]
    autocomplete_fields = ['customer']
    
    fieldsets = (
        ('Totales', {
            'fields': (
                ('subtotal_display', 'subtotal_bs_display'),
                ('tax_display', 'tax_bs_display'),
                ('total_display', 'total_bs_display'),
                'rate_display',
            ),
            'classes': ('tab', 'wide'),
            'description': 'Los totales se muestran en USD y Bs. según tasa del día'
        }),

        ('Pagos', {
            'fields': (
                'payment_summary_display',  # ← NUEVO
                ('paid_amount', 'change_amount'),
            ),
            'classes': ('tab', 'wide'),
            'description': 'Resumen de los pagos realizados en la orden de venta'
        }),
        ('Información', {
            'fields': ('number', 'customer', 'sale_order_number', 'status')
        }),
        ('Datos Fiscales del Emisor', {
            'fields': ('issuer_rif', 'issuer_name', 'issuer_address'),
            'classes': ('tab',),
        }),

        ('Información Adicional', {
            'fields': ('note',),
            'classes': ('tab',),
        }),

    )
    
    readonly_fields = ['date', 'subtotal', 'tax', 'total', 'user', 'created_at', 'updated_at','payment_summary_display', 'paid_amount', 'change_amount']


    # ✅ NUEVO: Métodos para mostrar pagos
    @admin.display(description='Monto Pagado')
    def paid_amount_display(self, obj):
        """Mostrar monto pagado con símbolo"""
        return f"$ {obj.paid_amount:.2f}"
    
    @admin.display(description='Resumen de Pagos')
    def payment_summary_display(self, obj):
        """Mostrar resumen de pagos con colores"""
        if not obj.payment_summary:
            return "No hay pagos registrados"
        
        html = '<div style="margin: 5px 0;">'
        
        for code, amount in obj.payment_summary.items():
            try:
                method = PaymentMethod.objects.get(code=code)
                name = method.name
            except PaymentMethod.DoesNotExist:
                name = code
            
            html += f'''
            <div style="display: flex; justify-content: space-between; 
                        padding: 4px 8px; margin: 2px 0; 
                        background: #f8f9fa; border-radius: 4px;">
                <span style="font-weight: bold;">{name}</span>
                <span style="color: #28a745;">$ {amount:.2f}</span>
            </div>
            '''
        
        if obj.change_amount > 0:
            html += f'''
            <div style="display: flex; justify-content: space-between; 
                        padding: 4px 8px; margin: 2px 0; 
                        background: #fff3cd; border-radius: 4px;">
                <span style="font-weight: bold;">🔄 Cambio</span>
                <span style="color: #856404;">$ {obj.change_amount:.2f}</span>
            </div>
            '''
        
        html += '</div>'
        
        # ✅ Usar mark_safe en lugar de format_html
        return mark_safe(html)

    class Media:
        js = ('admin/js/invoice_admin.js', 'admin/js/offline_manager.js',)

    
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

    @admin.display(description='Cliente')
    def customer_display(self, obj):
        if obj.customer:
            return f"{obj.customer.name} ({obj.customer.tax_id})"
        return obj.customer_name or "Sin cliente"
    
    def save_formset(self, request, form, formset, change):
        super().save_formset(request, form, formset, change)
        form.instance.calculate_totals()
        form.instance.save()