# django_erp/sales/admin.py
from django.contrib import admin
from django import forms
from django.utils.html import format_html
from django.urls import path
from django.contrib import messages
from django.core.exceptions import ValidationError
from unfold.admin import ModelAdmin as UnfoldModelAdmin
from unfold.admin import TabularInline as UnfoldTabularInline
from .models import Customer, SaleOrder, SaleLine
from .models import CashRegister, CashTransaction
from .helpers import get_open_register
from decimal import Decimal, ROUND_HALF_UP
from django.utils import timezone
from django_erp.configuration.models import Company, Currency
from django_erp.accounting.models import ExchangeRate
from .models import Payment, SaleInvoiceLine, SaleInvoice
from django_erp.configuration.models import PaymentMethod
from django.urls import path
from django.views.generic import TemplateView
from unfold.views import UnfoldModelAdminViewMixin
from unfold.widgets import UnfoldAdminTextInputWidget, UnfoldAdminSelectWidget, UnfoldAdminTextareaWidget
from .services import SaleReportService
from django_erp.configuration.mixins import CompanyFilterMixin
from .signals import order_confirmed, invoice_paid
from django_erp.inventory.models import Product, Location
from django_erp.inventory.models import Inventory
from django.db import transaction
from django_erp.inventory.services import WarehouseService, InventoryService
import logging
logger = logging.getLogger(__name__)
from django_erp.accounting.services import TaxService


# ============================================================
# ✅ FORMULARIO PARA FACTURA DE VENTA (INDEPENDIENTE)
# ============================================================

class SaleInvoiceForm(forms.ModelForm):
    """Formulario personalizado para facturas de venta independientes"""
    stock_display = forms.CharField(
        required=False,
        disabled=True,
        label="Stock Disponible",
        initial="0",
        help_text="Cantidad disponible en inventario"
    )
    # Campos para mostrar totales
    subtotal_display = forms.CharField(
        required=False,
        disabled=True,
        label="Subtotal (USD)",
        initial="0.00"
    )

    # ✅ NUEVOS: Campos para mostrar totales en Bs.
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
    
    class Meta:
        model = SaleInvoice
        fields = ['number', 'customer', 'sale_order', 'status', 'date_due', 'note']
        widgets = {
            'number': forms.TextInput(attrs={'readonly': 'readonly'}),
        }
    
    def __init__(self, *args, **kwargs):
        self._request = kwargs.pop('request', None)
        instance = kwargs.get('instance')
        super().__init__(*args, **kwargs)
        
        # ✅ Obtener tasa de cambio
        rate = ExchangeRate.get_today_rate('USD', 'BS')
        if rate:
            self.initial['rate_display'] = f"1 USD = Bs. {rate:.2f}"
        else:
            self.initial['rate_display'] = "No hay tasa configurada"
        
        # ✅ Si es una nueva factura, generar número automáticamente
        if not instance or not instance.pk:
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
            
            self.initial['number'] = f"FAC-VENTA-{datetime.now().strftime('%Y%m')}-{next_num:04d}"
            self.initial['status'] = 'PAID'
            
            customer_id = self._request.GET.get('customer') if self._request else None
            if customer_id:
                try:
                    customer = Customer.objects.get(id=customer_id)
                    self.initial['customer'] = customer.id
                except Customer.DoesNotExist:
                    pass
            
            # ✅ Inicializar totales en 0
            self.initial['subtotal_display'] = "0.00"
            self.initial['tax_display'] = "0.00"
            self.initial['total_display'] = "0.00"
            self.initial['subtotal_bs_display'] = "0.00"
            self.initial['tax_bs_display'] = "0.00"
            self.initial['total_bs_display'] = "0.00"
        
        # ✅ Si es una factura existente, mostrar totales
        if instance and instance.pk:
            self.initial['subtotal_display'] = f"{instance.subtotal:.2f}"
            self.initial['tax_display'] = f"{instance.tax:.2f}"
            self.initial['total_display'] = f"{instance.total:.2f}"
            
            if rate:
                self.initial['subtotal_bs_display'] = f"{(instance.subtotal * rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP):.2f}"
                self.initial['tax_bs_display'] = f"{(instance.tax * rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP):.2f}"
                self.initial['total_bs_display'] = f"{(instance.total * rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP):.2f}"
        
        # ✅ Hacer que sale_order sea opcional
        self.fields['sale_order'].required = False
        self.fields['sale_order'].help_text = "Opcional: Si la factura proviene de una orden de venta"
        self.fields['status'].choices = SaleInvoice.STATUS_CHOICES
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        
        if not instance.company_id:
            if self._request:
                company = getattr(self._request, 'current_company', None)
                if company:
                    instance.company = company
            
            if not instance.company_id:
                company = Company.get_active()
                if company:
                    instance.company = company
        
        if not instance.user_id and self._request:
            instance.user = self._request.user
        
        if instance.customer_id:
            if not instance.customer_name:
                instance.customer_name = instance.customer.name
                instance.customer_tax_id = instance.customer.tax_id
                instance.customer_address = instance.customer.address
        
        if commit:
            instance.save()
            self.save_m2m()
        
        return instance


# ============================================================
# ✅ FORMULARIO PARA LÍNEAS DE FACTURA
# ============================================================

class SaleInvoiceLineForm(forms.ModelForm):
    """Formulario personalizado para líneas de factura"""
    
    class Meta:
        model = SaleInvoiceLine
        fields = ['product', 'quantity', 'unit_price']
    
    def __init__(self, *args, **kwargs):
        self._request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        # Hacer el campo unit_price de solo lectura
        if 'unit_price' in self.fields:
            self.fields['unit_price'].widget.attrs.update({
                'readonly': 'readonly',
                'style': 'background-color: #f0f0f0; cursor: not-allowed;'
            })

    
    def save(self, commit=True):
        instance = super().save(commit=False)
        
        # Asignar compañía
        if not instance.company_id:
            if self._request:
                company = getattr(self._request, 'current_company', None)
                if company:
                    instance.company = company
            
            if not instance.company_id:
                company = Company.get_active()
                if company:
                    instance.company = company
        
        # Si tiene producto, copiar sus datos
        if instance.product_id:
            instance.product_code = instance.product.code
            instance.product_name = instance.product.name
        
        # Calcular subtotal
        instance.subtotal = instance.quantity * instance.unit_price
        
        if commit:
            instance.save()
            self.save_m2m()
        
        return instance


# ============================================================
# ✅ INLINE DE LÍNEAS DE FACTURA
# ============================================================

class SaleInvoiceLineInline(UnfoldTabularInline):
    """Inline de líneas de factura de venta"""
    model = SaleInvoiceLine
    form = SaleInvoiceLineForm
    extra = 1
    fields = ['product', 'stock_display', 'quantity', 'unit_price', 'subtotal']
    readonly_fields = ['subtotal', 'stock_display'] 
    autocomplete_fields = ['product']
    verbose_name_plural = "📦 Líneas de Productos/Servicios"


    # ✅ Definir stock_display como método
    @admin.display(description='Stock Disponible')
    def stock_display(self, obj):
        """Mostrar el stock disponible del producto"""
        if not obj or not obj.product_id:
            return "—"
        
        try:
            # Obtener la compañía del objeto o usar la actual
            company = obj.company if obj.company_id else None
            if not company:
                from django_erp.configuration.models import Company
                company = Company.get_active()
            
            # Calcular stock total
            from django_erp.inventory.models import Inventory
            stock = Inventory.objects.filter(
                product=obj.product,
                company=company
            ).aggregate(total=models.Sum('quantity'))['total'] or 0
            
            # Obtener la unidad del producto
            unit = obj.product.get_unit_display() if hasattr(obj.product, 'get_unit_display') else 'unidades'
            
            return f"{stock} {unit}" if stock > 0 else "Sin stock"
        except Exception as e:
            return "Error al obtener stock"

    def get_formset(self, request, obj=None, **kwargs):
        formset = super().get_formset(request, obj, **kwargs)
        class FormSetWithRequest(formset):
            def _construct_form(self, i, **kwargs):
                # ✅ Pasar el request al formulario
                kwargs['request'] = request
                return super()._construct_form(i, **kwargs)
        
        company = getattr(request, 'current_company', None)
        if company:
            formset.form.base_fields['product'].queryset = Product.objects.filter(
                company=company,
                is_active=True
            )
        else:
            formset.form.base_fields['product'].queryset = Product.objects.filter(is_active=True)
        
        return formset


# ============================================================
# ✅ FORMULARIO PARA PAGOS DE FACTURA (CORREGIDO)
# ============================================================

class SaleInvoicePaymentForm(forms.ModelForm):
    """Formulario personalizado para pagos de facturas"""
    
    class Meta:
        model = Payment
        fields = ['method', 'amount', 'reference', 'customer_bank']
    
    def __init__(self, *args, **kwargs):
        self._request = kwargs.pop('request', None)
        self._parent_instance = kwargs.pop('parent_instance', None)
        super().__init__(*args, **kwargs)
        
        if 'currency' in self.fields:
            self.fields['currency'].widget = forms.HiddenInput()
    
    def clean(self):
        """Validar que el método de pago tenga moneda por defecto"""
        cleaned_data = super().clean()
        method = cleaned_data.get('method')
        
        if method and not method.default_currency:
            raise ValidationError(
                f'El método de pago "{method.name}" no tiene una moneda por defecto configurada. '
                'Por favor, configura la moneda predeterminada en el método de pago.'
            )
        
        return cleaned_data
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        # ✅ Asignar la moneda del método de pago ANTES de guardar
        if instance.method and instance.method.default_currency:
            instance.currency = instance.method.default_currency
        else:
            # ✅ Fallback: intentar obtener USD
            try:
                from django_erp.configuration.models import Currency
                usd = Currency.objects.get(code='USD')
                instance.currency = usd
            except Currency.DoesNotExist:
                raise ValidationError("No se encontró la moneda USD como respaldo.")
        if self._parent_instance:
            instance.sale_invoice = self._parent_instance
            # ✅ Asegurar que sale_order sea None para pagos de factura
            instance.sale_order = None
        # Asignar compañía
        if not instance.company_id:
            if self._request:
                company = getattr(self._request, 'current_company', None)
                if company:
                    instance.company = company
            
            if not instance.company_id:
                company = Company.get_active()
                if company:
                    instance.company = company
        
        # Establecer estado por defecto
        if not instance.status:
            instance.status = 'COMPLETED'
        
        if commit:
            instance.save()
            self.save_m2m()
        
        return instance


# ============================================================
# ✅ INLINE DE PAGOS DE FACTURA (CORREGIDO)
# ============================================================

class SaleInvoicePaymentInline(UnfoldTabularInline):
    """Inline de pagos para facturas de venta"""
    model = Payment
    fk_name = 'sale_invoice'
    form = SaleInvoicePaymentForm
    extra = 1
    fields = ['method', 'amount', 'reference']
    autocomplete_fields = ['method']
    verbose_name_plural = "💳 Pagos del Cliente"

    
    def get_formset(self, request, obj=None, **kwargs):
        """Pasar la factura padre al formulario"""
        formset = super().get_formset(request, obj, **kwargs)
        
        # ✅ Crear una clase de formset que pase el parent_instance
        class FormSetWithParent(formset):
            def __init__(self, *args, **kwargs):
                self._parent_instance = obj  # ✅ La factura padre
                super().__init__(*args, **kwargs)
            
            def _construct_form(self, i, **kwargs):
                # ✅ Pasar el parent_instance al formulario
                kwargs['parent_instance'] = self._parent_instance
                kwargs['request'] = request
                return super()._construct_form(i, **kwargs)
        
        return FormSetWithParent


# ============================================================
# ✅ ADMIN DE FACTURA DE VENTA
# ============================================================

@admin.register(SaleInvoice)
class SaleInvoiceAdmin(CompanyFilterMixin, UnfoldModelAdmin):
    """Admin de facturas de venta - INDEPENDIENTE DE ORDENES"""
    
    form = SaleInvoiceForm
    
    list_display = [
        'number',
        'company_display',
        'customer',
        'date_issued',
        'subtotal_display',
        'tax_display',
        'total_display',
        'status_badge',
        'created_at'
    ]
    list_filter = ['status', 'date_issued', 'company']
    search_fields = ['number', 'customer__name', 'customer_tax_id', 'company__name']
    
    inlines = [SaleInvoiceLineInline, SaleInvoicePaymentInline]
    autocomplete_fields = ['customer']
    
    fieldsets = (
        ('Información de la Factura', {
            'fields': ('number', 'customer', 'status')
        }),
        ('Orden de Venta (opcional)', {
            'fields': ('sale_order',),
            'description': 'Si esta factura proviene de una orden de venta, selecciónala aquí.'
        }),

        # ✅ Totales en Tiempo Real - Igual que en órdenes de venta
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
            'classes': ('collapse',),
        }),
    )
    
    readonly_fields = ['date_issued', 'user', 'created_at', 'updated_at', 'subtotal', 'tax', 'total']
    
    class Media:
        js = ('admin/js/sale_invoice_admin.js',)
    
    @admin.display(description='Compañía', ordering='company__name')
    def company_display(self, obj):
        if obj.company:
            return format_html(
                '<span style="font-weight: 500;">{} - {}</span>',
                obj.company.code,
                obj.company.name
            )
        return "Sin compañía"
    
    @admin.display(description='Subtotal', ordering='subtotal')
    def subtotal_display(self, obj):
        # Calcular subtotal sumando las líneas
        subtotal = sum(line.subtotal for line in obj.lines.all())
        return f"$ {subtotal:.2f}"
    
    @admin.display(description='IVA', ordering='tax')
    def tax_display(self, obj):
        # Obtener la compañía activa del request
        company = getattr(self, '_current_company', None)
        if not company:
            company = Company.get_active()
        
        # Calcular subtotal y luego IVA con la tasa correcta
        subtotal = sum(line.subtotal for line in obj.lines.all())
        tax_rate = TaxService.get_current_vat_rate(company)
        tax = subtotal * (tax_rate / Decimal('100'))
        return f"$ {tax:.2f}"
    
    @admin.display(description='Total', ordering='total')
    def total_display(self, obj):
        company = getattr(self, '_current_company', None)
        if not company:
            company = Company.get_active()
        
        subtotal = sum(line.subtotal for line in obj.lines.all())
        tax_rate = TaxService.get_current_vat_rate(company)
        tax = subtotal * (tax_rate / Decimal('100'))
        total = subtotal + tax
        return f"$ {total:.2f}"

    # ✅ Agregar este método para guardar la compañía del request
    def get_queryset(self, request):
        self._current_company = getattr(request, 'current_company', None)
        return super().get_queryset(request)
    
    @admin.display(description='Estado', ordering='status')
    def status_badge(self, obj):
        colors = {
            'DRAFT': ('#6c757d', '📝 Borrador'),
            'ISSUED': ('#17a2b8', '📄 Emitida'),
            'PAID': ('#28a745', '✅ Pagada'),
            'CANCELLED': ('#dc3545', '❌ Anulada'),
        }
        color, label = colors.get(obj.status, ('#6c757d', obj.status))
        return format_html(
            '<span style="background: {}; color: white; padding: 2px 10px; border-radius: 12px; font-size: 12px;">{}</span>',
            color,
            label
        )
    def get_form(self, request, obj=None, **kwargs):
        """Limpiar banderas de sesión al abrir una nueva factura"""
        if obj is None:
            # Limpiar banderas de sesión para nueva factura
            for key in list(request.session.keys()):
                if key.startswith('invoice_'):
                    del request.session[key]
        return super().get_form(request, obj, **kwargs)

    def save_model(self, request, obj, form, change):
        """
        Guardar la factura y enviar señal si cambia a PAID
        """
        # ✅ Asignar compañía
        company = self._get_active_company(request)
        if company and hasattr(obj, 'company'):
            obj.company = company
        
        # ✅ Si tiene cliente, copiar sus datos
        if obj.customer_id:
            obj.customer_name = obj.customer.name
            obj.customer_tax_id = obj.customer.tax_id
            obj.customer_address = obj.customer.address
        
        if not obj.user:
            obj.user = request.user
        
        # ✅ Obtener el estado anterior (si existe)
        old_status = None
        if change and obj.pk:
            try:
                old_invoice = SaleInvoice.objects.get(pk=obj.pk)
                old_status = old_invoice.status
            except SaleInvoice.DoesNotExist:
                pass
        
        # ✅ Guardar la factura
        super(CompanyFilterMixin, self).save_model(request, obj, form, change)
        
        # ✅ Si cambió a PAID, enviar señal para registrar en caja
        if obj.status == 'PAID' and old_status != 'PAID':
            from .signals import invoice_paid
            invoice_paid.send(sender=SaleInvoice, invoice=obj, request=request)
            logger.info(f"   📨 Señal invoice_paid enviada para {obj.number}")

    def _register_cash_transaction(self, invoice, user):
        """Registrar transacción en caja desde una factura"""
        from .models import CashTransaction
        from .helpers import get_open_register
        from django_erp.configuration.models import PaymentMethod, Currency
        
        try:
            # ✅ Verificar que no exista ya una transacción para esta factura
            existing = CashTransaction.objects.filter(
                reference=invoice.number,
                type='SALE'
            ).first()
            
            if existing:
                logger.info(f"   ℹ️ Transacción ya existe para factura {invoice.number}")
                return
            
            # ✅ Obtener caja abierta
            register = get_open_register(user)
            
            # ✅ Crear transacción
            CashTransaction.objects.create(
                register=register,
                type='SALE',
                amount=invoice.total,
                description=f"Factura {invoice.number} - {invoice.customer_name}",
                reference=invoice.number,
                user=user,
                company=invoice.company,
            )
            
            # ✅ Recalcular totales de la caja
            register.calculate_totals()
            
            # ✅ Crear pago asociado a la factura
            default_method = PaymentMethod.objects.filter(
                company=invoice.company,
                is_active=True
            ).first()
            
            if default_method:
                from .models import Payment
                Payment.objects.create(
                    sale_invoice=invoice,
                    method=default_method,
                    currency=Currency.objects.get(code='USD'),
                    amount=invoice.total,
                    amount_usd=invoice.total,
                    reference=f"Pago factura {invoice.number}",
                    status='COMPLETED',
                    user=user,
                    company=invoice.company,
                )
            
            self.message_user(
                request,
                f'✅ Transacción registrada en caja por ${invoice.total:.2f}',
                messages.SUCCESS
            )
            
        except ValidationError as e:
            self.message_user(
                request,
                f'⚠️ No se pudo registrar en caja: {str(e)}',
                messages.WARNING
            )
        except Exception as e:
            logger.error(f"Error registrando transacción en caja: {e}")

    def _reduce_inventory(self, request, invoice):
        """
        Reducir el inventario para cada línea de la factura.
        Retorna la lista de movimientos creados.
        """
        from django_erp.inventory.models import Inventory, Location
        
        logger.info("=" * 80)
        logger.info("🔴 [_reduce_inventory] INICIANDO")
        logger.info(f"   Factura: {invoice.number}")
        
        company = invoice.company or getattr(request, 'current_company', None)
        if not company:
            company = Company.get_active()
        
        if not company:
            logger.error("   ❌ No hay compañía activa")
            raise ValidationError("No hay una compañía activa para reducir inventario.")
        
        logger.info(f"   Compañía: {company.code}")
        
        if not invoice.lines.exists():
            logger.warning("   ⚠️ La factura no tiene líneas")
            return []
        
        logger.info(f"   Líneas a procesar: {invoice.lines.count()}")
        
        movements_created = []
        
        for idx, line in enumerate(invoice.lines.all(), 1):
            logger.info(f"   📝 Procesando línea {idx}:")
            logger.info(f"      - Producto ID: {line.product_id}")
            logger.info(f"      - Producto: {line.product_name or 'Sin nombre'}")
            logger.info(f"      - Cantidad: {line.quantity}")
            logger.info(f"      - Precio: {line.unit_price}")
            
            if not line.product:
                logger.warning(f"      ⚠️ Línea sin producto, saltando...")
                continue
            
            if line.product.is_service:
                logger.info(f"      ℹ️ {line.product.name} es un servicio, no se reduce inventario")
                continue
            
            # ✅ Buscar ubicación para el producto
            location = None
            
            # 1. Buscar en el inventario (primer registro con stock)
            inventory_records = Inventory.objects.filter(
                product=line.product,
                company=company
            ).order_by('-quantity')
            
            for inv in inventory_records:
                if inv.quantity > 0 and inv.location:
                    location = inv.location
                    logger.info(f"      ✅ Ubicación con stock: {location.code} (stock: {inv.quantity})")
                    break
            
            # 2. Si no tiene inventario con stock, buscar cualquier ubicación activa
            if not location:
                location = Location.objects.filter(
                    company=company,
                    is_active=True
                ).first()
                if location:
                    logger.info(f"      ✅ Usando ubicación por defecto: {location.code}")
            
            if not location:
                logger.error(f"      ❌ No hay ubicación para el producto {line.product.name}")
                raise ValidationError(
                    f"No hay ubicación para el producto {line.product.name}. "
                    f"Configura una ubicación en Inventario > Ubicaciones."
                )
            
            # ✅ Verificar stock disponible
            stock = InventoryService.get_stock_by_location(
                line.product.id, 
                location.id, 
                company
            )
            logger.info(f"      - Stock disponible en {location.code}: {stock}")
            
            if stock < line.quantity:
                logger.error(f"      ❌ Stock insuficiente: {stock} < {line.quantity}")
                raise ValidationError(
                    f"Stock insuficiente para '{line.product.name}'. "
                    f"Disponible: {stock}, Requerido: {line.quantity}"
                )
            
            # ✅ Crear movimiento de salida
            logger.info("      🚀 Creando movimiento de salida...")
            movement = WarehouseService.create_exit(
                product_id=line.product.id,
                quantity=line.quantity,
                location_from_id=location.id,
                unit_price=line.unit_price,
                source_type='SALE',
                source_reference=invoice.number,
                note=f"Factura {invoice.number} - {invoice.customer_name or 'Sin cliente'}",
                user=request.user,
                company=company
            )
            movements_created.append(movement)
            logger.info(f"      ✅ Movimiento {movement.id} creado")
        
        logger.info(f"   ✅ {len(movements_created)} movimientos creados")
        logger.info("🔴 [_reduce_inventory] FINALIZADO")
        logger.info("=" * 80)
        
        return movements_created


    def save_formset(self, request, form, formset, change):
        """
        Guardar líneas y pagos de la factura.
        Después de guardar, procesar reducción de inventario y registro en caja.
        """
        logger.info("=" * 80)
        logger.info("🔴 [SaleInvoiceAdmin.save_formset] INICIANDO")
        
        # ✅ USAR BANDERA EN SESIÓN PARA EVITAR DUPLICADOS
        session_key = f'invoice_reduced_{form.instance.pk or "new"}'
        
        # Si ya se procesó esta factura en esta sesión, saltar
        if request.session.get(session_key):
            logger.info(f"   ℹ️ Factura ya procesada en esta sesión, saltando...")
            logger.info("🔴 [SaleInvoiceAdmin.save_formset] FINALIZADO (duplicado)")
            logger.info("=" * 80)
            return super().save_formset(request, form, formset, change)
        
        company = getattr(request, 'current_company', None)
        if not company:
            company = Company.get_active()
        
        logger.info(f"   Compañía para inlines: {company.code if company else 'N/A'}")
        
        # ✅ Obtener el estado actual de la factura ANTES de guardar los inlines
        invoice = form.instance
        old_status = None
        if change and invoice.pk:
            try:
                old_invoice = SaleInvoice.objects.get(pk=invoice.pk)
                old_status = old_invoice.status
                logger.info(f"   Estado anterior de la factura: {old_status}")
            except SaleInvoice.DoesNotExist:
                pass
        
        new_status = invoice.status
        logger.info(f"   Nuevo estado de la factura: {new_status}")
        
        # ✅ Guardar los inlines (líneas y pagos)
        instances = formset.save(commit=False)
        logger.info(f"   Instancias a guardar: {len(instances)}")
        
        for instance in instances:
            if hasattr(instance, 'company') and not instance.company_id:
                instance.company = company
                logger.info(f"   ✅ Compañía asignada a {instance.__class__.__name__}")
            
            if hasattr(instance, 'product') and instance.product:
                instance.product_code = instance.product.code
                instance.product_name = instance.product.name
            
            instance.save()
        
        formset.save_m2m()
        
        for obj in formset.deleted_objects:
            logger.info(f"   🗑️ Eliminando objeto: {obj}")
            obj.delete()
        
        # ✅ RECALCULAR TOTALES DESPUÉS DE GUARDAR LÍNEAS
        if invoice.pk:
            # Recargar la instancia desde la base de datos para tener los datos más recientes
            invoice.refresh_from_db()
            
            # Calcular totales desde las líneas
            subtotal = Decimal('0.00')
            for line in invoice.lines.all():
                subtotal += Decimal(str(line.subtotal))
            
            # Obtener tasa de IVA de la compañía
            company = invoice.company or Company.get_active()
            from django_erp.accounting.services import TaxService
            tax_rate = TaxService.get_current_vat_rate(company) if company else Decimal('16.00')
            
            tax = subtotal * (tax_rate / Decimal('100'))
            total = subtotal + tax
            
            # Asignar los totales calculados
            invoice.subtotal = subtotal.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            invoice.tax = tax.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            invoice.total = total.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            
            # Guardar solo los campos de totales
            invoice.save(update_fields=['subtotal', 'tax', 'total'])
            
            # ✅ Volver a recargar para asegurar que los valores están actualizados
            invoice.refresh_from_db()
            
            logger.info(f"   ✅ Totales recalculados: Subtotal={invoice.subtotal}, IVA={invoice.tax}, Total={invoice.total}")
        
        # ✅ PROCESAR REGISTRO EN CAJA Y REDUCCIÓN DE INVENTARIO
        is_new_paid = new_status == 'PAID' and (old_status is None or old_status != 'PAID')
        
        if is_new_paid:
            logger.info(f"   🎯 Factura {invoice.number} cambió a PAID")
            logger.info(f"   📊 Monto total de la factura: {invoice.total}")
            
            # ✅ 1. VERIFICAR Y REGISTRAR EN CAJA
            from .models import CashTransaction
            from .helpers import get_open_register
            from django_erp.configuration.models import PaymentMethod, Currency
            
            # Verificar que el monto total sea mayor a 0
            if invoice.total <= 0:
                logger.warning(f"   ⚠️ El total de la factura es {invoice.total}, no se registra en caja")
                self.message_user(
                    request,
                    f'⚠️ La factura tiene total {invoice.total}, no se registra en caja porque el monto es cero o negativo.',
                    messages.WARNING
                )
            else:
                # Verificar que no exista ya una transacción
                cash_exists = CashTransaction.objects.filter(
                    reference=invoice.number,
                    type='SALE'
                ).exists()
                
                if cash_exists:
                    logger.info(f"   ℹ️ Transacción de caja ya existe para {invoice.number}")
                    existing = CashTransaction.objects.filter(
                        reference=invoice.number,
                        type='SALE'
                    ).first()
                    logger.info(f"   ℹ️ Monto existente: {existing.amount}")
                else:
                    try:
                        register = get_open_register(request.user)
                        logger.info(f"   ✅ Caja abierta: {register.number}")
                        
                        # ✅ CREAR LA TRANSACCIÓN CON EL MONTO CORRECTO
                        transaction = CashTransaction.objects.create(
                            register=register,
                            type='SALE',
                            amount=invoice.total,  # ✅ Usar el total calculado
                            description=f"Factura {invoice.number} - {invoice.customer_name}",
                            reference=invoice.number,
                            user=request.user,
                            company=invoice.company,
                        )
                        logger.info(f"   ✅ Transacción creada con monto: {transaction.amount}")
                        
                        # Recalcular totales de la caja
                        register.calculate_totals()
                        logger.info(f"   ✅ Totales de caja recalculados")
                        
                        self.message_user(
                            request,
                            f'✅ Transacción registrada en caja por ${invoice.total:.2f}',
                            messages.SUCCESS
                        )
                        
                        # Crear pago si no existe
                        payment_exists = Payment.objects.filter(
                            sale_invoice=invoice,
                            status='COMPLETED'
                        ).exists()
                        
                        if not payment_exists:
                            default_method = PaymentMethod.objects.filter(
                                company=invoice.company,
                                is_active=True
                            ).first()
                            
                            if default_method:
                                try:
                                    usd = Currency.objects.get(code='USD')
                                except Currency.DoesNotExist:
                                    usd = None
                                
                                if usd:
                                    Payment.objects.create(
                                        sale_invoice=invoice,
                                        method=default_method,
                                        currency=usd,
                                        amount=invoice.total,
                                        amount_usd=invoice.total,
                                        reference=f"Pago factura {invoice.number}",
                                        status='COMPLETED',
                                        user=request.user,
                                        company=invoice.company,
                                    )
                                    logger.info(f"   ✅ Pago creado para factura {invoice.number}")
                        
                    except ValidationError as e:
                        logger.warning(f"   ⚠️ No se pudo registrar en caja: {e}")
                        if not request.session.get(f'invoice_cash_warned_{invoice.pk}'):
                            self.message_user(
                                request,
                                f'⚠️ No se pudo registrar en caja: {str(e)}',
                                messages.WARNING
                            )
                            request.session[f'invoice_cash_warned_{invoice.pk}'] = True
                    except Exception as e:
                        logger.error(f"   ❌ Error al registrar en caja: {e}")
                        import traceback
                        logger.error(f"   Traceback: {traceback.format_exc()}")
                        if not request.session.get(f'invoice_cash_error_{invoice.pk}'):
                            self.message_user(
                                request,
                                f'⚠️ Error al registrar en caja: {str(e)}',
                                messages.ERROR
                            )
                            request.session[f'invoice_cash_error_{invoice.pk}'] = True
            
            # ✅ 2. VERIFICAR Y REDUCIR INVENTARIO
            from django_erp.inventory.models import Movement
            already_reduced = Movement.objects.filter(
                source_reference=invoice.number,
                source_type='SALE'
            ).exists()
            
            if already_reduced:
                logger.info(f"   ℹ️ El inventario ya fue reducido para {invoice.number}")
            else:
                if not invoice.lines.exists():
                    logger.warning(f"   ⚠️ La factura no tiene líneas, no se reduce inventario")
                    if not request.session.get(f'invoice_warned_{invoice.pk}'):
                        self.message_user(
                            request,
                            f'⚠️ La factura no tiene líneas, no se puede reducir inventario',
                            messages.WARNING
                        )
                        request.session[f'invoice_warned_{invoice.pk}'] = True
                else:
                    logger.info(f"   📊 Líneas a procesar: {invoice.lines.count()}")
                    try:
                        movements = self._reduce_inventory(request, invoice)
                        if movements:
                            logger.info(f"   ✅ {len(movements)} movimientos creados")
                            if not request.session.get(f'invoice_success_{invoice.pk}'):
                                self.message_user(
                                    request,
                                    f'✅ Inventario reducido para la factura {invoice.number} ({len(movements)} movimientos)',
                                    messages.SUCCESS
                                )
                                request.session[f'invoice_success_{invoice.pk}'] = True
                    except Exception as e:
                        logger.error(f"   ❌ Error al reducir inventario: {e}")
                        import traceback
                        logger.error(f"   Traceback: {traceback.format_exc()}")
                        if not request.session.get(f'invoice_error_{invoice.pk}'):
                            self.message_user(
                                request,
                                f'❌ Error al reducir inventario: {str(e)}',
                                messages.ERROR
                            )
                            request.session[f'invoice_error_{invoice.pk}'] = True
                        # Revertir el estado a ISSUED si no se pudo reducir
                        invoice.status = 'ISSUED'
                        invoice.save(update_fields=['status'])
                        logger.info("   ↩️ Estado revertido a ISSUED")
                        raise
        else:
            logger.info(f"   ℹ️ No se requiere procesamiento (status: {new_status}, old: {old_status})")
        
        # ✅ Marcar como procesado en esta sesión
        request.session[session_key] = True
        
        logger.info("🔴 [SaleInvoiceAdmin.save_formset] FINALIZADO")
        logger.info("=" * 80)
        
        return super().save_formset(request, form, formset, change)


# ============================================================
# ✅ ADMIN DE CLIENTES (SIN CAMBIOS)
# ============================================================

@admin.register(Customer)
class CustomerAdmin(CompanyFilterMixin, UnfoldModelAdmin):
    """Admin de clientes"""
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


# ============================================================
# ✅ FORMULARIO PARA LÍNEAS DE VENTA (ORDEN) - SIN CAMBIOS
# ============================================================

class SaleLineInlineForm(forms.ModelForm):
    """Formulario personalizado para líneas de venta"""
    class Meta:
        model = SaleLine
        fields = '__all__'
    
    def __init__(self, *args, **kwargs):
        self._request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        
        if not instance.company_id:
            if hasattr(instance, 'order') and instance.order_id:
                try:
                    order = SaleOrder.objects.get(id=instance.order_id)
                    instance.company = order.company
                except SaleOrder.DoesNotExist:
                    pass
            
            if not instance.company_id and self._request:
                company = getattr(self._request, 'current_company', None)
                if company:
                    instance.company = company
            
            if not instance.company_id:
                company = Company.get_active()
                if company:
                    instance.company = company
        
        if commit:
            instance.save()
            self.save_m2m()
        
        return instance


# ============================================================
# ✅ INLINE DE LÍNEAS DE VENTA - SIN CAMBIOS
# ============================================================

class SaleLineInline(UnfoldTabularInline):
    """Inline de líneas de orden de venta con visualización de stock"""
    model = SaleLine
    form = SaleLineInlineForm
    extra = 1
    fields = ['product', 'stock_display', 'quantity', 'unit_price', 'subtotal']
    readonly_fields = ['subtotal', 'stock_display']
    autocomplete_fields = ['product']
    verbose_name_plural = "📦 Líneas de Productos/Servicios"

    @admin.display(description='Stock Disponible')
    def stock_display(self, obj):
        """Mostrar el stock disponible del producto"""
        if not obj or not obj.product_id:
            return "—"
        try:
            company = obj.company if hasattr(obj, 'company') and obj.company_id else None
            if not company:
                company = Company.get_active()
            
            stock = Inventory.objects.filter(
                product=obj.product,
                company=company
            ).aggregate(total=models.Sum('quantity'))['total'] or 0
            
            unit = obj.product.get_unit_display() if hasattr(obj.product, 'get_unit_display') else 'unidades'
            return f"{stock} {unit}" if stock > 0 else "Sin stock"
        except Exception:
            return "Error al obtener stock"

    def get_formset(self, request, obj=None, **kwargs):
        formset = super().get_formset(request, obj, **kwargs)
        
        class FormSetWithRequest(formset):
            def _construct_form(self, i, **kwargs):
                kwargs['request'] = request
                return super()._construct_form(i, **kwargs)

        company = getattr(request, 'current_company', None)
        if company:
            formset.form.base_fields['product'].queryset = Product.objects.filter(
                company=company,
                is_active=True
            )
        else:
            formset.form.base_fields['product'].queryset = Product.objects.filter(is_active=True)
            
        return formset


# ============================================================
# ✅ FORMULARIO PARA PAGOS DE ORDEN DE VENTA - SIN CAMBIOS
# ============================================================

class PaymentInlineForm(forms.ModelForm):
    """Formulario personalizado para pagos de órdenes de venta"""
    class Meta:
        model = Payment
        fields = ['method', 'amount', 'reference', 'customer_bank']

    def __init__(self, *args, **kwargs):
        self._request = kwargs.pop('request', None)
        self._parent_instance = kwargs.pop('parent_instance', None)
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()
        method = cleaned_data.get('method')
        if method and not method.default_currency:
            raise ValidationError(
                f'El método de pago "{method.name}" no tiene una moneda por defecto configurada.'
            )
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        
        # Asignar moneda predeterminada del método o USD por defecto
        if instance.method and instance.method.default_currency:
            instance.currency = instance.method.default_currency
        else:
            try:
                usd = Currency.objects.get(code='USD')
                instance.currency = usd
            except Currency.DoesNotExist:
                pass

        if self._parent_instance:
            instance.sale_order = self._parent_instance

        if not instance.company_id:
            if self._request:
                company = getattr(self._request, 'current_company', None)
                if company:
                    instance.company = company
            if not instance.company_id:
                company = Company.get_active()
                if company:
                    instance.company = company

        if not instance.status:
            instance.status = 'COMPLETED'

        if commit:
            instance.save()
            self.save_m2m()
        return instance


# ============================================================
# ✅ INLINE DE PAGOS DE ORDEN DE VENTA - SIN CAMBIOS
# ============================================================

class PaymentInline(UnfoldTabularInline):
    """Inline de pagos para órdenes de venta estilo Factura"""
    model = Payment
    fk_name = 'sale_order'
    form = PaymentInlineForm
    extra = 1
    fields = ['method', 'amount', 'reference']
    autocomplete_fields = ['method']
    verbose_name_plural = "💳 Pagos del Cliente"

    def get_formset(self, request, obj=None, **kwargs):
        formset = super().get_formset(request, obj, **kwargs)
        
        class FormSetWithParent(formset):
            def __init__(self, *args, **kwargs):
                self._parent_instance = obj
                super().__init__(*args, **kwargs)

            def _construct_form(self, i, **kwargs):
                kwargs['parent_instance'] = self._parent_instance
                kwargs['request'] = request
                return super()._construct_form(i, **kwargs)

        return FormSetWithParent


# ============================================================
# ✅ FORMULARIO DE ORDEN DE VENTA - SIN CAMBIOS
# ============================================================

class SaleOrderForm(forms.ModelForm):
    """Formulario personalizado para órdenes de venta"""
    
    subtotal_display = forms.CharField(
        required=False,
        disabled=True,
        label="Subtotal (USD)",
        initial="0.00"
    )
    
    subtotal_bs_display = forms.CharField(
        required=False,
        disabled=True,
        label="Subtotal (Bs.)",
        initial="0.00"
    )
    
    tax_display = forms.CharField(
        required=False,
        disabled=True,
        label="IVA (USD)",
        initial="0.00"
    )
    
    tax_bs_display = forms.CharField(
        required=False,
        disabled=True,
        label="IVA (Bs.)",
        initial="0.00"
    )
    
    total_display = forms.CharField(
        required=False,
        disabled=True,
        label="Total (USD)",
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
        model = SaleOrder
        fields = ['number', 'customer', 'status', 'note']
        widgets = {
            'number': forms.TextInput(attrs={'readonly': 'readonly'}),
        }

    def __init__(self, *args, **kwargs):
        self._request = kwargs.pop('request', None)
        instance = kwargs.get('instance')
        
        super().__init__(*args, **kwargs)
        
        if self._request and not instance:
            company = getattr(self._request, 'current_company', None)
            if company:
                self.instance.company = company
            else:
                fallback = Company.get_active()
                if fallback:
                    self.instance.company = fallback
        
        company = self.instance.company or Company.get_active()
        from django_erp.accounting.services import TaxService
        tax_rate = TaxService.get_current_vat_rate(company) if company else Decimal('16.00')
        rate = ExchangeRate.get_today_rate('USD', 'BS')
        
        if rate:
            self.initial['rate_display'] = f"1 USD = Bs. {rate:.2f}"
        else:
            self.initial['rate_display'] = "No hay tasa configurada"
        
        if instance and instance.pk:
            subtotal = instance.subtotal
            tax = instance.tax
            total = instance.total
            
            self.initial['subtotal_display'] = f"{subtotal:.2f}"
            self.initial['tax_display'] = f"{tax:.2f}"
            self.initial['total_display'] = f"{total:.2f}"
            
            if rate:
                self.initial['subtotal_bs_display'] = f"{(subtotal * rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP):.2f}"
                self.initial['tax_bs_display'] = f"{(tax * rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP):.2f}"
                self.initial['total_bs_display'] = f"{(total * rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP):.2f}"
        else:
            self.initial['subtotal_display'] = "0.00"
            self.initial['tax_display'] = "0.00"
            self.initial['total_display'] = "0.00"
            self.initial['subtotal_bs_display'] = "0.00"
            self.initial['tax_bs_display'] = "0.00"
            self.initial['total_bs_display'] = "0.00"
        
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

    def clean(self):
        cleaned_data = super().clean()
        status = cleaned_data.get('status')
        
        if status == 'CONFIRMED':
            from .helpers import has_open_register
            
            user = None
            if hasattr(self, '_request') and self._request:
                user = self._request.user
            elif self.instance and self.instance.user:
                user = self.instance.user
            
            if user and not has_open_register(user):
                from django.urls import reverse
                from django.utils.html import format_html
                
                open_cash_url = reverse('admin:sales_cashregister_add')
                error_msg = format_html(
                    '❌ No hay una caja abierta. '
                    '<a href="{}" target="_blank" style="font-weight: bold;">Haz clic aquí para abrir una caja</a>',
                    open_cash_url
                )
                self.add_error('status', error_msg)
        
        return cleaned_data


# ============================================================
# ✅ ADMIN DE ÓRDENES DE VENTA - SIN CAMBIOS
# ============================================================

@admin.action(description='🔄 Reconfirmar orden (forzar reducción de stock)')
def reconfirm_order_action(modeladmin, request, queryset):
    from .services import SaleService
    from .signals import order_confirmed
    
    for order in queryset:
        try:
            print(f"🔴 Reconfirmando orden {order.number}")
            
            try:
                get_open_register(request.user)
            except ValidationError as e:
                modeladmin.message_user(request, f"Error con {order.number}: {str(e)}", messages.ERROR)
                continue
            
            if not order.lines.exists():
                modeladmin.message_user(request, f"La orden {order.number} no tiene líneas.", messages.WARNING)
                continue
            
            for line in order.lines.all():
                if line.product and not line.product.is_service:
                    print(f"   Reduciendo stock de {line.product.name} x {line.quantity}")
                    try:
                        from django_erp.inventory.services import WarehouseService
                        WarehouseService.create_exit(
                            product_id=line.product.id,
                            quantity=line.quantity,
                            location_from_id=line.location.id if line.location else None,
                            unit_price=line.unit_price,
                            source_type='SALE',
                            source_reference=order.number,
                            note=f"Venta {order.number} - Reconfirmación",
                            user=request.user,
                            company=order.company
                        )
                        print(f"   ✅ Stock reducido para {line.product.name}")
                    except Exception as e:
                        print(f"   ❌ Error al reducir stock: {e}")
                        modeladmin.message_user(request, f"Error con {order.number}: {e}", messages.ERROR)
                        continue
            
            existing = CashTransaction.objects.filter(
                reference=order.number,
                type='SALE'
            ).exists()
            
            if not existing:
                print(f"   Registrando en caja...")
                order._status_changed_by = request.user
                order_confirmed.send(sender=SaleOrder, order=order)
                print(f"   ✅ Registro en caja completado")
            else:
                print(f"   ⚠️ La transacción ya existe para {order.number}")
            
            modeladmin.message_user(request, f'✅ Orden {order.number} reconfirmada exitosamente', messages.SUCCESS)
            
        except Exception as e:
            print(f"❌ Error al reconfirmar {order.number}: {e}")
            modeladmin.message_user(request, f"Error con {order.number}: {e}", messages.ERROR)


class SalesReportView(UnfoldModelAdminViewMixin, TemplateView):
    title = "Reporte de Ventas"
    permission_required = ('sales.can_view_reports',)
    template_name = "admin/sales/sales_report.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        company = getattr(self.request, 'current_company', None)
        if not company:
            company = Company.get_active()
        
        grand_totals = SaleReportService.get_grand_totals(company=company)
        labels, totals = SaleReportService.get_totals_by_period(
            period_type='day', 
            days_back=30,
            company=company
        )
        
        context['grand_totals'] = grand_totals
        context['chart_labels'] = labels
        context['chart_totals'] = totals
        
        context['company_name'] = company.name if company else "Todas"
        context['company_code'] = company.code if company else ""
        
        return context



@admin.register(SaleOrder)
class SaleOrderAdmin(CompanyFilterMixin, UnfoldModelAdmin):
    form = SaleOrderForm
    
    list_display = ['number', 'customer', 'company_display', 'date', 'total', 'status', 'created_at']
    list_filter = ['status', 'date', 'company']
    search_fields = ['number', 'customer__name', 'company__name', 'company__code']
    
    inlines = [SaleLineInline, PaymentInline]
    
    autocomplete_fields = ['customer']
    actions = [reconfirm_order_action]
    
    fieldsets = (
        ('Información de la Orden', {
            'fields': ('number', 'customer', 'status')
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
        js = ('admin/js/sale_order_admin.js',)

    @admin.display(description='Compañía', ordering='company__name')
    def company_display(self, obj):
        if obj.company:
            return f"{obj.company.code} - {obj.company.name}"
        return "Sin compañía"

    def get_form(self, request, obj=None, **kwargs):
        form_class = super().get_form(request, obj, **kwargs)
        
        def form_with_request(*args, **kwargs):
            kwargs['request'] = request
            return form_class(*args, **kwargs)
        
        return form_with_request
    
    def save_model(self, request, obj, form, change):
        if not obj.company_id:
            company = getattr(request, 'current_company', None)
            if company:
                obj.company = company
            else:
                company = Company.get_active()
                if company:
                    obj.company = company
                else:
                    self.message_user(request, '❌ No hay una compañía activa.', messages.ERROR)
                    raise forms.ValidationError('No hay una compañía activa configurada en el sistema.')
        
        if not obj.user:
            obj.user = request.user
        
        obj._status_changed_by = request.user
        
        super().save_model(request, obj, form, change)

    def get_urls(self):
        custom_view = self.admin_site.admin_view(SalesReportView.as_view(model_admin=self))
        urls = super().get_urls()
        custom_urls = [
            path('sales-report/', custom_view, name='sales_salesreport'),
        ]
        return custom_urls + urls

    def save_formset(self, request, form, formset, change):
        from .services import SaleService
        from .signals import order_confirmed
        from decimal import Decimal
        
        company = form.instance.company
        if not company:
            company = getattr(request, 'current_company', None)
            if not company:
                company = Company.get_active()
        
        instances = formset.save(commit=False)
        for instance in instances:
            if hasattr(instance, 'company') and not instance.company_id:
                instance.company = company
                if isinstance(instance, Payment):
                    instance.save(update_fields=['company'])
        
        for instance in instances:
            instance.save()
        
        formset.save_m2m()
        
        for obj in formset.deleted_objects:
            obj.delete()
        
        obj = form.instance
        
        subtotal = Decimal('0.00')
        for line in obj.lines.all():
            subtotal += Decimal(str(line.subtotal))
        
        company = obj.company or Company.get_active()
        from django_erp.accounting.services import TaxService
        tax_rate = TaxService.get_current_vat_rate(company) if company else Decimal('16.00')
        
        tax = subtotal * (tax_rate / Decimal('100'))
        total = subtotal + tax
        
        obj.subtotal = subtotal
        obj.tax = tax
        obj.total = total
        
        obj.save()
        
        new_status = form.cleaned_data.get('status')
        
        if new_status == 'CONFIRMED':
            from django_erp.inventory.models import Movement
            has_movement = Movement.objects.filter(
                source_reference=obj.number,
                source_type='SALE'
            ).exists()
            
            if has_movement:
                from .models import CashTransaction
                has_transaction = CashTransaction.objects.filter(
                    reference=obj.number,
                    type='SALE'
                ).exists()
                
                if not has_transaction and obj.total > 0:
                    obj._status_changed_by = request.user
                    order_confirmed.send(sender=SaleOrder, order=obj)
                    self.message_user(request, f'✅ Transacción en caja registrada para {obj.number}', messages.SUCCESS)
                
                for line in obj.lines.all():
                    if line.product and not line.location:
                        from django_erp.inventory.models import Inventory
                        inventory = Inventory.objects.filter(product=line.product, company=company).first()
                        if inventory and inventory.location:
                            line.location = inventory.location
                            line.save()
                return
            
            try:
                get_open_register(request.user)
            except ValidationError as e:
                self.message_user(request, str(e), messages.ERROR)
                return
            
            try:
                SaleService.confirm_order(obj, request.user)
            except Exception as e:
                self.message_user(request, f"Error al confirmar: {e}", messages.ERROR)
                obj.status = 'DRAFT'
                obj.save()
                return
            
            self.message_user(request, f'✅ Orden {obj.number} confirmada exitosamente', messages.SUCCESS)
        
        for line in obj.lines.all():
            if line.product and not line.location:
                from django_erp.inventory.models import Inventory
                inventory = Inventory.objects.filter(product=line.product, company=company).first()
                if inventory and inventory.location:
                    line.location = inventory.location
                    line.save()


# ============================================================
# ✅ ADMIN DE CAJA - SIN CAMBIOS
# ============================================================

@admin.action(description='✅ Abrir caja seleccionada')
def open_register_action(modeladmin, request, queryset):
    for register in queryset:
        if register.status == 'OPEN':
            modeladmin.message_user(request, f'La caja {register.number} ya está abierta.', messages.WARNING)
            continue
        
        if CashRegister.objects.filter(user=register.user, status='OPEN').exists():
            modeladmin.message_user(
                request, 
                f'❌ El usuario {register.user.username} ya tiene una caja abierta.', 
                messages.ERROR
            )
            continue
        
        register.status = 'OPEN'
        register.opened_at = timezone.now()
        register.save()
        modeladmin.message_user(request, f'✅ Caja {register.number} abierta exitosamente.', messages.SUCCESS)


@admin.action(description='🔒 Cerrar caja seleccionada')
def close_register_action(modeladmin, request, queryset):
    for register in queryset:
        if register.status != 'OPEN':
            modeladmin.message_user(request, f'La caja {register.number} no está abierta.', messages.WARNING)
            continue
        
        register.calculate_totals()
        
        if register.counted_total is None:
            register.counted_total = register.expected_total
            register.difference = 0
        
        register.status = 'CLOSED'
        register.closed_at = timezone.now()
        register.save()
        
        modeladmin.message_user(
            request, 
            f'✅ Caja {register.number} cerrada exitosamente. Total: {register.expected_total:.2f} USD', 
            messages.SUCCESS
        )


class CashTransactionInline(UnfoldTabularInline):
    """Inline para mostrar transacciones dentro de la caja"""
    model = CashTransaction
    extra = 0
    readonly_fields = ['type', 'amount', 'description', 'reference', 'user', 'created_at']
    fields = ['type', 'amount', 'description', 'reference', 'user', 'created_at']
    can_delete = False
    max_num = 0  # No permitir agregar desde aquí
    
    @admin.display(description='Tipo')
    def type_display(self, obj):
        return obj.get_type_display()
    
    def has_add_permission(self, request, obj=None):
        return False


# ============================================================
# FORMULARIO DE CAJA
# ============================================================

class CashRegisterForm(forms.ModelForm):
    """Formulario para apertura y cierre de caja"""
    
    class Meta:
        model = CashRegister
        fields = ['initial_amount']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # ✅ Si es una caja existente (edición), mostrar campos para cerrar
        if self.instance and self.instance.pk:
            # Agregar campo para dinero contado
            self.fields['counted_total'] = forms.DecimalField(
                label='💰 Dinero Contado',
                required=False,
                help_text='Ingresa el total de dinero contado al cerrar la caja.',
                widget=forms.NumberInput(attrs={
                    'step': '0.01',
                    'min': '0',
                    'placeholder': '0.00',
                })
            )
            
            
            # Agregar campo para estado con widget de Unfold
            self.fields['status'] = forms.ChoiceField(
                label='Estado',
                choices=CashRegister.STATUS_CHOICES,
                widget=UnfoldAdminSelectWidget(attrs={'class': 'form-control'})
            )
            
            # Agregar campo para nota con widget de Unfold
            self.fields['note'] = forms.CharField(
                label='Nota',
                required=False,
                widget=UnfoldAdminTextareaWidget(attrs={'rows': 3})
            )
    
    def clean(self):
        cleaned_data = super().clean()
        
        # ✅ Validar que si se cierra la caja, se ingrese el dinero contado
        if self.instance and self.instance.pk:
            status = cleaned_data.get('status')
            counted_total = cleaned_data.get('counted_total')
            
            if status == 'CLOSED' and counted_total is None:
                raise forms.ValidationError(
                    'Debes ingresar el dinero contado para cerrar la caja.'
                )
        
        return cleaned_data


# ============================================================
# ADMIN DE CAJA
# ============================================================

@admin.register(CashRegister)
class CashRegisterAdmin(CompanyFilterMixin, UnfoldModelAdmin):
    """Admin de caja - Apertura y cierre simplificado"""
    
    form = CashRegisterForm
    
    list_display = [
        'number',
        'user',
        'opened_at',
        'status_badge',
        'expected_total',
        'difference',
        'transactions_count',
    ]
    
    list_filter = ['status', 'date']
    search_fields = ['number', 'user__username']
    
    # ✅ Inline para ver transacciones
    inlines = [CashTransactionInline]
    
    readonly_fields = [
        'number',
        'user',
        'opened_at',
        'closed_at',
        'date',
        'total_sales',
        'total_expenses',
        'total_withdrawals',
        'expected_total',
        'difference',
        'created_at',
        'updated_at',
        'company',
    ]
    
    actions = []
    
    # ============================================================
    # MÉTODOS DE DISPLAY
    # ============================================================
    
    @admin.display(description='Estado')
    def status_badge(self, obj):
        colors = {
            'OPEN': ('#28a745', '🟢 Abierta'),
            'CLOSED': ('#6c757d', '🔒 Cerrada'),
            'APPROVED': ('#17a2b8', '✅ Aprobada'),
            'CANCELLED': ('#dc3545', '❌ Cancelada'),
        }
        color, label = colors.get(obj.status, ('#6c757d', obj.status))
        return format_html(
            '<span style="background: {}; color: white; padding: 2px 10px; border-radius: 12px; font-size: 12px;">{}</span>',
            color,
            label
        )
    
    @admin.display(description='Transacciones')
    def transactions_count(self, obj):
        count = obj.transactions.count()
        if count > 0:
            return format_html(
                '<span style="background: #17a2b8; color: white; padding: 2px 10px; border-radius: 12px; font-size: 12px;">{} movimientos</span>',
                count
            )
        return '-'
    
    # ============================================================
    # CONTROL DE CAMPOS SEGÚN EL CONTEXTO
    # ============================================================
    
    def get_fields(self, request, obj=None):
        """Mostrar diferentes campos según el contexto"""
        
        if obj is None:
            # ✅ NUEVA CAJA: solo initial_amount
            return ['initial_amount']
        
        else:
            # ✅ EDITAR CAJA ABIERTA: campos para cerrar
            if obj.status == 'OPEN':
                return ['status', 'counted_total', 'note']
            
            # ✅ CAJA CERRADA: todo readonly (solo información)
            else:
                return [
                    'number', 'user', 'opened_at', 'closed_at', 'date',
                    'status', 'initial_amount', 'total_sales', 'total_expenses',
                    'total_withdrawals', 'expected_total', 'counted_total',
                    'difference', 'note', 'company'
                ]
    
    def get_readonly_fields(self, request, obj=None):
        """Controlar qué campos son de solo lectura"""
        
        if obj is None:
            # ✅ NUEVA CAJA: initial_amount es editable
            return []
        
        else:
            # ✅ CAJA ABIERTA: status, counted_total y note son EDITABLES
            if obj.status == 'OPEN':
                return []  # Todos los campos visibles son editables
            
            # ✅ CAJA CERRADA: todos readonly
            return self.readonly_fields
    
    # ============================================================
    # GUARDAR
    # ============================================================
    
    def save_model(self, request, obj, form, change):
        """Guardar caja con campos automáticos"""
        
        # ✅ Si es NUEVA caja (apertura)
        if not change:
            # Asignar todo automáticamente
            obj.user = request.user
            obj.status = 'OPEN'
            
            # Asignar compañía activa
            company = getattr(request, 'current_company', None)
            if not company:
                company = Company.get_active()
            if company:
                obj.company = company
            
            # Verificar que no tenga otra caja abierta
            if CashRegister.objects.filter(user=obj.user, status='OPEN').exists():
                self.message_user(
                    request,
                    f'❌ El usuario {obj.user.username} ya tiene una caja abierta.',
                    messages.ERROR
                )
                raise forms.ValidationError('Ya tienes una caja abierta.')
            
            # Guardar
            super().save_model(request, obj, form, change)
            
            self.message_user(
                request,
                f'✅ Caja #{obj.number} abierta con ${obj.initial_amount:.2f}',
                messages.SUCCESS
            )
        
        # ✅ Si es EDITAR (cerrar caja)
        else:
            old_obj = CashRegister.objects.get(pk=obj.pk)
            
            # ✅ Si la caja estaba abierta y se cambia a CLOSED
            if old_obj.status == 'OPEN' and obj.status == 'CLOSED':
                # Validar que se haya ingresado el dinero contado
                if obj.counted_total is None:
                    self.message_user(
                        request,
                        '❌ Debes ingresar el dinero contado para cerrar la caja.',
                        messages.ERROR
                    )
                    raise forms.ValidationError('El dinero contado es obligatorio.')
                
                # Calcular totales y diferencia
                obj.calculate_totals()
                obj.closed_at = timezone.now()
                
                # Guardar
                super().save_model(request, obj, form, change)
                
                self.message_user(
                    request,
                    f'✅ Caja #{obj.number} cerrada. Diferencia: ${obj.difference:.2f}',
                    messages.SUCCESS
                )
            
            # ✅ Si no hay cambio de estado o es otro cambio, guardar normal
            else:
                super().save_model(request, obj, form, change)
    
    # ============================================================
    # PERMISOS
    # ============================================================
    
    def has_delete_permission(self, request, obj=None):
        return False
    
    def get_actions(self, request):
        return {}
    
    # ============================================================
    # VISTAS PERSONALIZADAS
    # ============================================================
    
    def add_view(self, request, form_url='', extra_context=None):
        """Personalizar título al abrir caja"""
        extra_context = extra_context or {}
        extra_context['title'] = 'Abrir Caja'
        return super().add_view(request, form_url, extra_context=extra_context)
    
    def change_view(self, request, object_id, form_url='', extra_context=None):
        """Personalizar título al cerrar caja"""
        extra_context = extra_context or {}
        obj = CashRegister.objects.get(pk=object_id)
        
        if obj.status == 'OPEN':
            extra_context['title'] = f'Cerrar Caja #{obj.number}'
        else:
            extra_context['title'] = f'Caja #{obj.number}'
        
        return super().change_view(request, object_id, form_url, extra_context=extra_context)


    def get_inlines(self, request, obj=None):
        """Mostrar transacciones SOLO cuando se edita una caja existente"""
        if obj is not None:
            # Si es una caja existente, mostrar las transacciones
            return [CashTransactionInline]
        # Si es nueva caja, NO mostrar transacciones
        return []


# ============================================================
# ADMIN DE TRANSACCIONES DE CAJA (Vista independiente)
# ============================================================

@admin.register(CashTransaction)
class CashTransactionAdmin(CompanyFilterMixin, UnfoldModelAdmin):
    """Admin de transacciones de caja - Vista independiente"""
    
    list_display = [
        'register',
        'type_badge',
        'amount_display',
        'description',
        'reference',
        'user',
        'created_at'
    ]
    
    list_filter = ['type', 'company', 'register__status']
    search_fields = ['description', 'reference', 'register__number', 'user__username']
    readonly_fields = ['uuid', 'created_at']
    autocomplete_fields = ['register', 'user']
    
    fieldsets = (
        ('Información de la Transacción', {
            'fields': ('register', 'type', 'amount', 'description', 'reference')
        }),
        ('Auditoría', {
            'fields': ('uuid', 'user', 'created_at'),
            'classes': ('collapse',),
        }),
    )
    
    @admin.display(description='Tipo', ordering='type')
    def type_badge(self, obj):
        colors = {
            'SALE': ('#28a745', '💰 Venta'),
            'EXPENSE': ('#dc3545', '📤 Gasto'),
            'WITHDRAWAL': ('#ffc107', '🏦 Retiro'),
            'DEPOSIT': ('#17a2b8', '📥 Depósito'),
            'ADJUSTMENT': ('#6c757d', '⚖️ Ajuste'),
        }
        color, label = colors.get(obj.type, ('#6c757d', obj.type))
        return format_html(
            '<span style="background: {}; color: white; padding: 2px 10px; border-radius: 12px; font-size: 11px;">{}</span>',
            color,
            label
        )
    
    @admin.display(description='Monto')
    def amount_display(self, obj):
        return f"$ {obj.amount:.2f}"
    
    def has_add_permission(self, request):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False