# django_erp/purchasing/admin.py
from django.contrib import admin
from django import forms
from django.utils.html import format_html
from django.contrib import messages
from decimal import Decimal
from unfold.admin import ModelAdmin as UnfoldModelAdmin
from unfold.admin import TabularInline as UnfoldTabularInline
from .models import Supplier, PurchaseOrder, PurchaseLine, PurchasePayment
from django_erp.configuration.models import ExchangeRate, Company
from django_erp.configuration.mixins import CompanyFilterMixin
import logging
import traceback
from .models import PurchaseInvoice, PurchaseInvoiceLine

logger = logging.getLogger(__name__)


# ============================================================
# ADMIN: PROVEEDORES
# ============================================================

@admin.register(Supplier)
class SupplierAdmin(CompanyFilterMixin, UnfoldModelAdmin):
    """Admin de proveedores con multicompañía"""

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
# INLINES
# ============================================================

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

    def get_formset(self, request, obj=None, **kwargs):
        formset = super().get_formset(request, obj, **kwargs)
        from django_erp.configuration.models import Currency, CompanyBankAccount

        # Moneda por defecto: USD
        try:
            usd = Currency.objects.get(code='USD')
            formset.form.base_fields['currency'].initial = usd.id
        except Currency.DoesNotExist:
            pass

        # Cuenta bancaria por defecto
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


class PurchaseInvoiceInline(UnfoldTabularInline):
    """Inline de facturas de compra en la orden"""
    model = PurchaseInvoice
    extra = 0
    fields = ['number', 'date_issued', 'total', 'status']
    readonly_fields = ['number', 'date_issued', 'total', 'status']
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


# ============================================================
# FORMULARIO DE ORDEN DE COMPRA
# ============================================================

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

        # Obtener tasa de cambio y IVA
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

            self.initial['subtotal_display'] = f"{subtotal:.2f}"
            self.initial['tax_display'] = f"{tax:.2f}"
            self.initial['total_display'] = f"{total:.2f}"

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

        if not (instance and instance.pk):
            self.initial['number'] = f"COMPRA-{datetime.now().strftime('%Y%m%d')}-{next_num:04d}"
            self.fields['number'].disabled = True
            self.initial['status'] = 'DRAFT'

        # Configurar opciones de estado según el estado actual
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


# ============================================================
# ACCIONES PERSONALIZADAS
# ============================================================

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


# ============================================================
# ADMIN: ÓRDENES DE COMPRA
# ============================================================

@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(CompanyFilterMixin, UnfoldModelAdmin):
    """Admin de órdenes de compra con multicompañía"""

    form = PurchaseOrderForm

    # ✅ Listado con columna de compañía
    list_display = [
        'number',
        'company_display',
        'supplier',
        'date',
        'expected_delivery',
        'subtotal',
        'tax',
        'total',
        'status',
        'created_at'
    ]

    # ✅ Filtros incluyendo compañía
    list_filter = ['status', 'date', 'company']

    # ✅ Búsqueda incluyendo compañía
    search_fields = ['number', 'supplier__name', 'company__name', 'company__code']

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

    # ============================================================
    # MÉTODOS PERSONALIZADOS
    # ============================================================

    @admin.display(description='Compañía', ordering='company__name')
    def company_display(self, obj):
        """Mostrar la compañía con formato y colores"""
        if obj.company:
            colors = {
                'MAIN': '#2d6a4f',
                'COL': '#1e3a5f',
                'MX': '#d4a017',
                'ES': '#c1121f',
            }
            color = colors.get(obj.company.code, '#6c757d')
            return format_html(
                '<span style="font-weight: 500; color: {};">{} - {}</span>',
                color,
                obj.company.code,
                obj.company.name
            )
        return "Sin compañía"

    def get_form(self, request, obj=None, **kwargs):
        """Pasar el request al formulario"""
        form = super().get_form(request, obj, **kwargs)
        form._request = request
        return form

    def _resolve_company(self, request):
        """
        Resolver la compañía activa con prioridad clara y consistente.
        Se usa tanto para la orden como para sus líneas/pagos, evitando
        que ambas resoluciones diverjan dentro de la misma petición.
        """
        company = getattr(request, 'current_company', None)
        if not company:
            company = Company.get_active()
        return company

    def save_model(self, request, obj, form, change):
        """Guardar la orden y procesar cambios de estado."""
        
        # ✅ ASIGNAR COMPAÑÍA A LA ORDEN
        if not obj.company_id:
            company = self._resolve_company(request)
            if company:
                obj.company = company
            else:
                self.message_user(request, '❌ No hay una compañía activa. Configura una compañía antes de continuar.', messages.ERROR)
                raise forms.ValidationError('No hay una compañía activa configurada en el sistema.')
        
        # ✅ ✅ ✅ ASEGURAR QUE STATUS NO SEA NONE (¡ESTA ES LA CLAVE PARA EVITAR EL ERROR!)
        if not obj.status:
            obj.status = 'DRAFT'
            print(f"⚠️ Status era None, asignando DRAFT para {obj.number}")
        
        # ✅ Obtener el estado anterior
        old_status = None
        if change and obj.pk:
            try:
                old_status = PurchaseOrder.objects.get(pk=obj.pk).status
            except PurchaseOrder.DoesNotExist:
                pass

        new_status = form.cleaned_data.get('status')
        
        # ✅ SI NEW_STATUS ES NONE, USAR EL OBJ.STATUS
        if new_status is None:
            new_status = obj.status

        logger.debug(
            "save_model orden=%s compañía=%s estado_anterior=%s estado_nuevo=%s",
            obj.number, obj.company.code if obj.company else 'NINGUNA', old_status, new_status
        )

        # ✅ Asegurar tax_rate
        if not change and not obj.tax_rate:
            company = Company.get_active()
            obj.tax_rate = company.tax_rate if company else Decimal('16.00')

        if not obj.user:
            obj.user = request.user

        # ✅ ✅ ✅ GUARDAR LA ORDEN (con status asegurado)
        super().save_model(request, obj, form, change)

        # ✅ Recalcular totales
        if obj.pk:
            obj.calculate_totals()
            obj.save(update_fields=['subtotal', 'tax', 'total'])

        # ✅ Procesar cambio de estado
        if old_status != new_status:
            self._process_status_change(request, obj, old_status, new_status)

    def _process_status_change(self, request, obj, old_status, new_status):
        """Procesar cambios de estado de la orden."""
        from .services import PurchaseService, PurchaseInvoiceService

        try:
            if new_status == 'ORDERED':
                logger.info("Confirmando orden %s", obj.number)
                PurchaseService.confirm_order(obj, request.user)
                self.message_user(request, f'✅ Orden {obj.number} confirmada', messages.SUCCESS)

            elif new_status == 'RECEIVED':
                logger.info("Recibiendo orden %s", obj.number)
                PurchaseService.receive_order(obj, request.user)
                obj.refresh_from_db()

                # Generar factura
                if not obj.invoiced:
                    invoice = PurchaseInvoiceService.create_invoice_from_purchase_order(
                        obj.id, request.user
                    )
                    self.message_user(
                        request,
                        f'✅ Orden recibida. Factura {invoice.number} generada.',
                        messages.SUCCESS
                    )

            elif new_status == 'CANCELLED':
                logger.info("Cancelando orden %s", obj.number)
                PurchaseService.cancel_order(obj, request.user)
                self.message_user(request, f'✅ Orden {obj.number} cancelada', messages.SUCCESS)

        except Exception as e:
            logger.exception("Error procesando cambio de estado de %s", obj.number)
            self.message_user(request, f'❌ Error: {str(e)}', messages.ERROR)
            obj.status = old_status
            obj.save(update_fields=['status'])

    def save_formset(self, request, form, formset, change):
        """
        Guardar líneas/pagos y recalcular totales.

        ✅ ASIGNACIÓN DE COMPAÑÍA A LOS INLINES (líneas, pagos):
        Se usa la MISMA resolución que save_model (self._resolve_company) y,
        como red de seguridad adicional, si por algún motivo no hay compañía
        resuelta aquí, se hereda directamente de la orden padre (form.instance),
        que en este punto YA fue guardada con su company_id (save_model corre
        antes que save_formset dentro del flujo de Django admin).
        """
        parent_order = form.instance
        company = self._resolve_company(request) or getattr(parent_order, 'company', None)

        logger.debug(
            "save_formset orden=%s compañía_para_inlines=%s",
            parent_order.number if parent_order.pk else '(nueva)',
            company.code if company else 'NINGUNA'
        )

        instances = formset.save(commit=False)

        for instance in instances:
            # ✅ Asignar compañía a la línea/pago si no la trae
            if hasattr(instance, 'company') and not instance.company_id:
                # Preferir la compañía resuelta del request; si no hay,
                # heredar de la orden padre como último recurso.
                if company:
                    instance.company = company
                elif getattr(instance, 'order_id', None):
                    instance.company = instance.order.company
                elif getattr(instance, 'purchase_order_id', None):
                    instance.company = instance.purchase_order.company
            instance.save()

        # ✅ Guardar relaciones ManyToMany
        formset.save_m2m()

        # ✅ Eliminar objetos marcados para borrar
        for obj in formset.deleted_objects:
            obj.delete()

        # ✅ Recalcular totales
        obj = form.instance
        if obj.pk:
            obj.calculate_totals()
            obj.save(update_fields=['subtotal', 'tax', 'total', 'updated_at'])

        logger.debug("Total recalculado para %s: %s", obj.number, obj.total)


# ============================================================
# ADMIN: FACTURAS DE COMPRA
# ============================================================

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
class PurchaseInvoiceAdmin(CompanyFilterMixin, UnfoldModelAdmin):
    """Admin de facturas de compra con multicompañía"""

    list_display = [
        'number',
        'company_display',
        'supplier',
        'date_issued',
        'total',
        'status',
        'created_at'
    ]
    list_filter = ['status', 'date_issued', 'company']
    search_fields = ['number', 'supplier__name', 'supplier_rif', 'company__name']

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

    @admin.display(description='Compañía', ordering='company__name')
    def company_display(self, obj):
        if obj.company:
            return format_html(
                '<span style="font-weight: 500;">{} - {}</span>',
                obj.company.code,
                obj.company.name
            )
        return "Sin compañía"

    def save_model(self, request, obj, form, change):
        if not obj.user:
            obj.user = request.user
        super().save_model(request, obj, form, change)
        obj.calculate_totals()
        obj.save(update_fields=['subtotal', 'tax', 'total'])