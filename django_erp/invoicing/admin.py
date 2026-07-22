# invoicing/admin.py
from django.contrib import admin
from django import forms
from django.utils.html import format_html
from django.urls import reverse
from django.apps import apps
from unfold.admin import ModelAdmin as UnfoldModelAdmin
from unfold.admin import TabularInline as UnfoldTabularInline
from .models import Invoice, InvoiceLine
from django_erp.configuration.models import Company, PaymentMethod, Currency
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
                'payment_summary_display',
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
    
    readonly_fields = ['date', 'subtotal', 'tax', 'total', 'user', 'created_at', 'updated_at','payment_summary_display']


    # ✅ NUEVO: Métodos para mostrar pagos
    @admin.display(description='Monto Pagado')
    def paid_amount_display(self, obj):
        """Mostrar monto pagado con símbolo"""
        return f"$ {obj.paid_amount:.2f}"
    
    @admin.display(description='Resumen de Pagos')
    def payment_summary_display(self, obj):
        """Mostrar resumen de pagos SIMPLIFICADO (solo lo que el cliente pagó)"""
        if not obj.payment_summary:
            return "No hay pagos registrados"
        
        html = '<div style="margin: 5px 0; max-width: 350px;">'
        
        # ✅ Agrupar pagos por moneda
        bs_payments = []
        usd_payments = []
        
        for key, data in obj.payment_summary.items():
            currency_code = data.get('currency', 'USD')
            if currency_code == 'BS':
                bs_payments.append(data)
            elif currency_code == 'USD':
                usd_payments.append(data)
        
        # ✅ Calcular totales
        total_bs = sum(data.get('amount', 0) for data in bs_payments)
        total_usd = sum(data.get('amount', 0) for data in usd_payments)
        
        # ✅ Mostrar pagos en Bolívares (si hay)
        if bs_payments:
            html += '<div style="margin-bottom: 8px;">'
            html += '<div style="font-weight: bold; color: #856404; margin-bottom: 4px; font-size: 13px;">💵 Pagos en Bolívares:</div>'
            for data in bs_payments:
                amount = data.get('amount', 0)
                formatted = f"Bs. {amount:,.2f}".replace(',', '.').replace('.', ',', 1)
                html += f'''
                <div style="display: flex; justify-content: space-between; 
                            padding: 4px 10px; margin: 2px 0; 
                            background: #fff8e1; border-radius: 4px;">
                    <span style="font-size: 13px;">{data.get('method_name', data.get('method'))}</span>
                    <span style="font-weight: bold; color: #856404; font-size: 13px;">{formatted}</span>
                </div>
                '''
            html += '</div>'
        
        # ✅ Mostrar pagos en Dólares (si hay)
        if usd_payments:
            html += '<div style="margin-bottom: 8px;">'
            html += '<div style="font-weight: bold; color: #1e7e34; margin-bottom: 4px; font-size: 13px;">💰 Pagos en Dólares:</div>'
            for data in usd_payments:
                amount = data.get('amount', 0)
                formatted = f"$ {amount:,.2f}"
                html += f'''
                <div style="display: flex; justify-content: space-between; 
                            padding: 4px 10px; margin: 2px 0; 
                            background: #e8f5e9; border-radius: 4px;">
                    <span style="font-size: 13px;">{data.get('method_name', data.get('method'))}</span>
                    <span style="font-weight: bold; color: #1e7e34; font-size: 13px;">{formatted}</span>
                </div>
                '''
            html += '</div>'
        
        # ✅ SECCIÓN: Totales
        html += '<div style="margin-top: 10px; padding-top: 10px; border-top: 2px solid #2d6a4f;">'
        
        if total_bs > 0:
            formatted_bs = f"Bs. {total_bs:,.2f}".replace(',', '.').replace('.', ',', 1)
            html += f'''
            <div style="display: flex; justify-content: space-between; 
                        padding: 4px 10px; margin: 2px 0; 
                        background: #d4edda; border-radius: 4px;">
                <span style="font-weight: bold; font-size: 14px;">✅ Total Pagado</span>
                <span style="font-weight: bold; color: #155724; font-size: 14px;">{formatted_bs}</span>
            </div>
            '''
        
        if total_usd > 0:
            html += f'''
            <div style="display: flex; justify-content: space-between; 
                        padding: 4px 10px; margin: 2px 0; 
                        background: #d4edda; border-radius: 4px;">
                <span style="font-weight: bold; font-size: 14px;">✅ Total Pagado (USD)</span>
                <span style="font-weight: bold; color: #155724; font-size: 14px;">$ {total_usd:,.2f}</span>
            </div>
            '''
        
        html += '</div>'
        
        # ✅ ✅ ✅ SECCIÓN: Vuelto (SOLO si aplica)
        # ✅ Usar change_summary que tiene el vuelto por moneda
        if obj.change_summary:
            html += '<div style="margin-top: 10px; padding-top: 10px; border-top: 2px solid #ddd;">'
            html += '<div style="font-weight: bold; color: #856404; margin-bottom: 4px; font-size: 13px;">🔄 Vuelto:</div>'
            
            for currency_code, amount in obj.change_summary.items():
                if currency_code == 'BS':
                    formatted = f"Bs. {amount:,.2f}".replace(',', '.').replace('.', ',', 1)
                    bg = '#fff3cd'
                    color = '#856404'
                elif currency_code == 'USD':
                    formatted = f"$ {amount:,.2f}"
                    bg = '#e8f5e9'
                    color = '#1e7e34'
                else:
                    formatted = f"{currency_code} {amount:,.2f}"
                    bg = '#f8f9fa'
                    color = '#6c757d'
                
                html += f'''
                <div style="display: flex; justify-content: space-between; 
                            padding: 4px 10px; margin: 2px 0; 
                            background: {bg}; border-radius: 4px;">
                    <span style="font-weight: bold; font-size: 13px;">Vuelto en {currency_code}</span>
                    <span style="font-weight: bold; color: {color}; font-size: 13px;">{formatted}</span>
                </div>
                '''
            html += '</div>'
        else:
            # ✅ Si no hay vuelto, mostrar que está pagado
            html += '''
            <div style="margin-top: 10px; padding-top: 10px; border-top: 2px solid #28a745;">
                <div style="display: flex; justify-content: space-between; 
                            padding: 4px 10px; margin: 2px 0; 
                            background: #d4edda; border-radius: 4px;">
                    <span style="font-weight: bold; font-size: 14px; color: #155724;">✅ Pagado</span>
                    <span style="font-weight: bold; color: #155724; font-size: 14px;">Sin vuelto</span>
                </div>
            </div>
            '''
        
        html += '</div>'
        
        if html.strip():
            return mark_safe(html)
        return "No hay pagos registrados"

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