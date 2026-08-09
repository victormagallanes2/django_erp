# django_erp/purchasing/admin.py
from django.contrib import admin
from django import forms
from django.core.exceptions import ValidationError  # ✅ IMPORTANTE: Debe estar aquí
from django.utils.html import format_html
from django.contrib import messages
from django.utils import timezone
from decimal import Decimal
from unfold.admin import ModelAdmin as UnfoldModelAdmin
from unfold.admin import TabularInline as UnfoldTabularInline
from .models import Supplier, PurchaseOrder, PurchaseLine, PurchasePayment
from .models import PurchaseInvoice, PurchaseInvoiceLine
from django_erp.configuration.models import ExchangeRate, Company
from django_erp.configuration.mixins import CompanyFilterMixin
import logging

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
        from django_erp.inventory.models import Product, Location
        
        company = getattr(request, 'current_company', None)
        if company:
            formset.form.base_fields['product'].queryset = Product.objects.filter(
                company=company,
                is_active=True
            )
            formset.form.base_fields['location'].queryset = Location.objects.filter(
                company=company,
                is_active=True
            )
        else:
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
    """Formulario de orden de compra - Con nuevos estados"""

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
        instance = kwargs.get('instance')
        super().__init__(*args, **kwargs)

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

        # ✅ CONFIGURAR OPCIONES DE ESTADO SEGÚN EL ESTADO ACTUAL
        if instance and instance.pk:
            current_status = instance.status
            
            # ✅ MOSTRAR SOLO LAS OPCIONES VÁLIDAS SEGÚN EL ESTADO ACTUAL
            if current_status == 'DRAFT':
                self.fields['status'].choices = [
                    ('DRAFT', '📝 Borrador'),
                    ('SENT', '📤 Enviar al Proveedor'),
                    ('CANCELLED', '❌ Cancelar'),
                ]
            elif current_status == 'SENT':
                self.fields['status'].choices = [
                    ('SENT', '📤 Enviado al Proveedor'),
                    ('CONFIRMED', '✅ Confirmar por Proveedor'),
                    ('CANCELLED', '❌ Cancelar'),
                ]
            elif current_status == 'CONFIRMED':
                self.fields['status'].choices = [
                    ('CONFIRMED', '✅ Confirmado por Proveedor'),
                    ('CANCELLED', '❌ Cancelar'),
                ]
                self.fields['status'].help_text = (
                    "La recepción ya no se elige aquí manualmente: al confirmar "
                    "esta orden se creó una Nota de Recibo en Borrador en "
                    "Inventario. Confírmala allí cuando llegue la mercancía "
                    "y la orden pasará a 'Recibido' automáticamente."
                )
            elif current_status == 'RECEIVED':
                self.fields['status'].choices = [
                    ('RECEIVED', '📦 Recibido'),
                ]
            elif current_status == 'CANCELLED':
                self.fields['status'].choices = [
                    ('CANCELLED', '❌ Cancelado'),
                ]
        else:
            # Para nuevas órdenes
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

            self.initial['number'] = f"COMPRA-{datetime.now().strftime('%Y%m%d')}-{next_num:04d}"
            self.fields['number'].disabled = True
            self.initial['status'] = 'DRAFT'
            self.fields['status'].choices = [
                ('DRAFT', '📝 Borrador'),
                ('SENT', '📤 Enviar al Proveedor'),
            ]

    def clean(self):
        cleaned_data = super().clean()
        status = cleaned_data.get('status')
        instance = self.instance
        
        # ✅ VALIDAR TRANSICIONES DE ESTADO
        if instance and instance.pk and status != instance.status:
            from .services import PurchaseService
            
            # Verificar si la transición es válida
            if not PurchaseService.can_transition(instance, status):
                raise ValidationError(
                    f"No se puede cambiar de '{instance.get_status_display()}' a "
                    f"'{dict(PurchaseOrder.STATUS_CHOICES).get(status, status)}'"
                )
        
        return cleaned_data


# ============================================================
# ADMIN: ÓRDENES DE COMPRA
# ============================================================

@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(CompanyFilterMixin, UnfoldModelAdmin):
    """Admin de órdenes de compra - Con nuevo flujo de estados"""

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
        'status_badge',
        'created_at'
    ]

    # ✅ Filtros incluyendo compañía
    list_filter = ['status', 'date', 'company']

    # ✅ Búsqueda incluyendo compañía
    search_fields = ['number', 'supplier__name', 'company__name', 'company__code']

    inlines = [PurchaseLineInline, PurchasePaymentInline, PurchaseInvoiceInline]
    actions = []  # El flujo es por estado, no por acciones masivas
    autocomplete_fields = ['supplier']

    fieldsets = (
        ('Información de la Orden', {
            'fields': ('number', 'supplier', 'expected_delivery', 'status')
        }),
        ('Seguimiento', {
            'fields': ('sent_date', 'confirmed_date', 'received_date'),
            'classes': ('collapse',),
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

    readonly_fields = ['user', 'date', 'sent_date', 'confirmed_date', 'received_date', 'created_at', 'updated_at']

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

    @admin.display(description='Estado', ordering='status')
    def status_badge(self, obj):
        """Mostrar badge de estado con colores y emojis"""
        colors = {
            'DRAFT': ('#6c757d', '📝 Borrador'),
            'SENT': ('#ffc107', '📤 Enviado'),
            'CONFIRMED': ('#17a2b8', '✅ Confirmado'),
            'RECEIVED': ('#28a745', '📦 Recibido'),
            'CANCELLED': ('#dc3545', '❌ Cancelado'),
        }
        color, label = colors.get(obj.status, ('#6c757d', obj.status))
        return format_html(
            '<span style="background: {}; color: white; padding: 4px 12px; border-radius: 12px; font-size: 12px; font-weight: 500;">{}</span>',
            color,
            label
        )

    def get_form(self, request, obj=None, **kwargs):
        """Pasar el request al formulario"""
        form = super().get_form(request, obj, **kwargs)
        form._request = request
        return form

    def _resolve_company(self, request):
        """
        Resolver la compañía activa con prioridad clara y consistente.
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
                self.message_user(
                    request,
                    '❌ No hay una compañía activa. Configura una compañía antes de continuar.',
                    messages.ERROR
                )
                raise ValidationError('No hay una compañía activa configurada en el sistema.')
        
        # ✅ ASEGURAR QUE STATUS NO SEA NONE
        if not obj.status:
            obj.status = 'DRAFT'
            logger.warning(f"⚠️ Status era None, asignando DRAFT para {obj.number}")
        
        # ✅ Obtener el estado anterior ANTES de guardar
        old_status = None
        if change and obj.pk:
            try:
                old_order = PurchaseOrder.objects.get(pk=obj.pk)
                old_status = old_order.status
                logger.info(f"🔍 Estado actual en BD: {old_status}, Nuevo estado: {obj.status}")
            except PurchaseOrder.DoesNotExist:
                pass

        # ✅ Obtener el nuevo estado del formulario
        new_status = form.cleaned_data.get('status')
        if new_status is None:
            new_status = obj.status

        logger.info(f"📝 Procesando orden {obj.number}: {old_status} → {new_status}")

        # ✅ Si no hay cambio de estado, guardar normalmente
        if old_status == new_status:
            logger.info(f"ℹ️ No hay cambio de estado para {obj.number}")
            if not obj.user:
                obj.user = request.user
            super().save_model(request, obj, form, change)
            if obj.pk:
                obj.calculate_totals()
                obj.save(update_fields=['subtotal', 'tax', 'total'])
            return

        # ✅ Si es una orden NUEVA (no existe fila previa en BD), no hay
        # una "transición" real que validar/procesar vía PurchaseService
        # (no existe un estado anterior contra el cual comparar). Se
        # guarda directamente con el estado elegido en el formulario.
        if not change or old_status is None:
            if not obj.user:
                obj.user = request.user
            super().save_model(request, obj, form, change)
            if obj.pk:
                obj.calculate_totals()
                obj.save(update_fields=['subtotal', 'tax', 'total'])
            return

        # ✅ Asegurar que el usuario esté asignado
        if not obj.user:
            obj.user = request.user

        # ✅ IMPORTANTE: Verificar si la transición es válida ANTES de guardar
        # ✅ FIX: se pasa old_status explícitamente porque en este punto
        # obj.status YA fue sobreescrito por Django con el nuevo valor
        # (form._post_clean() ya volcó cleaned_data sobre la instancia).
        # Sin esto, can_transition comparaba new_status contra sí mismo
        # y la validación fallaba siempre, bloqueando cualquier cambio
        # de estado.
        from .services import PurchaseService
        if not PurchaseService.can_transition(obj, new_status, current_status=old_status):
            self.message_user(
                request,
                f'❌ No se puede cambiar de "{dict(PurchaseOrder.STATUS_CHOICES).get(old_status, old_status)}" a "{dict(PurchaseOrder.STATUS_CHOICES).get(new_status, new_status)}"',
                messages.ERROR
            )
            # Revertir al estado anterior
            obj.status = old_status if old_status else 'DRAFT'
            super().save_model(request, obj, form, change)
            return

        # ✅ FIX: Guardar la orden con el ESTADO ANTERIOR (old_status),
        # NO con el nuevo. Antes se guardaba ya con obj.status=new_status,
        # así que cuando PurchaseService.send_order() / confirm_order_
        # from_supplier() / receive_order() / cancel_order() revisaban
        # order.status para validar su precondición (p. ej. "solo se
        # puede enviar una orden en Borrador"), la orden YA figuraba en
        # el estado nuevo en la BD y la precondición siempre fallaba.
        # Ahora el nuevo estado (y sus efectos secundarios: fechas, nota
        # de recibo, factura, movimientos de inventario, etc.) lo aplica
        # PurchaseService dentro de _process_status_change().
        obj.status = old_status
        super().save_model(request, obj, form, change)

        # ✅ Recalcular totales
        if obj.pk:
            obj.calculate_totals()
            obj.save(update_fields=['subtotal', 'tax', 'total'])

        # ✅ PROCESAR CAMBIO DE ESTADO (aplica el nuevo estado vía servicio)
        logger.info(f"🔄 Procesando cambio de estado: {old_status} → {new_status}")
        self._process_status_change(request, obj, old_status, new_status)

    def _process_status_change(self, request, obj, old_status, new_status):
        """Procesar cambios de estado con el nuevo flujo."""
        from .services import PurchaseService

        try:
            # ✅ VERIFICAR QUE EL NUEVO ESTADO SEA DIFERENTE AL ANTERIOR
            if old_status == new_status:
                logger.info(f"ℹ️ No hay cambio de estado para {obj.number}")
                return

            logger.info(f"🔄 Procesando: {old_status} → {new_status} para {obj.number}")

            if new_status == 'SENT':
                logger.info(f"📤 Enviando orden {obj.number} al proveedor")
                PurchaseService.send_order(obj, request.user)
                self.message_user(
                    request,
                    f'✅ Orden {obj.number} enviada al proveedor exitosamente',
                    messages.SUCCESS
                )

            elif new_status == 'CONFIRMED':
                logger.info(f"✅ Confirmando orden {obj.number} por proveedor")
                PurchaseService.confirm_order_from_supplier(obj, request.user)
                self.message_user(
                    request,
                    f'✅ Orden {obj.number} confirmada por el proveedor. '
                    f'Se creó una Nota de Recibo en Borrador en Inventario; '
                    f'confírmala allí cuando llegue la mercancía.',
                    messages.SUCCESS
                )

            elif new_status == 'RECEIVED':
                logger.info(f"📦 Recibiendo orden {obj.number}")
                PurchaseService.receive_order(obj, request.user)
                self.message_user(
                    request,
                    f'✅ Orden {obj.number} recibida exitosamente. '
                    f'Se confirmó su nota de recibo automáticamente.',
                    messages.SUCCESS
                )

            elif new_status == 'CANCELLED':
                logger.info(f"❌ Cancelando orden {obj.number}")
                PurchaseService.cancel_order(obj, request.user)
                self.message_user(
                    request,
                    f'✅ Orden {obj.number} cancelada exitosamente',
                    messages.SUCCESS
                )

        except ValidationError as e:
            logger.warning(f"⚠️ Validación fallida para {obj.number}: {str(e)}")
            self.message_user(request, f'⚠️ {str(e)}', messages.WARNING)
            # Revertir al estado anterior
            if old_status:
                obj.status = old_status
                obj.save(update_fields=['status'])
                logger.info(f"↩️ Revertido {obj.number} a {old_status}")

        except Exception as e:
            logger.exception(f"❌ Error procesando cambio de estado de {obj.number}")
            self.message_user(request, f'❌ Error: {str(e)}', messages.ERROR)
            # Revertir al estado anterior
            if old_status:
                obj.status = old_status
                obj.save(update_fields=['status'])
                logger.info(f"↩️ Revertido {obj.number} a {old_status}")
            raise

    def save_formset(self, request, form, formset, change):
        """
        Guardar líneas/pagos y recalcular totales.
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
        from django_erp.inventory.models import Product
        
        company = getattr(request, 'current_company', None)
        if company:
            formset.form.base_fields['product'].queryset = Product.objects.filter(
                company=company,
                is_active=True
            )
        else:
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