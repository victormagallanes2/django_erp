# inventory/admin.py
from django.contrib import admin
from django.utils.html import format_html
from simple_history.admin import SimpleHistoryAdmin
from unfold.admin import ModelAdmin as UnfoldModelAdmin
from unfold.admin import TabularInline as UnfoldTabularInline
from .models import (
    Product, Location, Movement,
    Inventory, ValuationMethod, PhysicalCount
)
from django_erp.configuration.models import ExchangeRate, Currency
from django_erp.configuration.mixins import CompanyFilterMixin
from .services import InventoryService
from .models import DeliveryNote, DeliveryNoteLine, ReceiptNote, ReceiptNoteLine


# ============================================================
# ADMIN: PRODUCTOS (ANTIGUO WAREHOUSE)
# ============================================================

@admin.register(Product)
class ProductAdmin(CompanyFilterMixin, SimpleHistoryAdmin, UnfoldModelAdmin):
    """Admin de productos con precios en USD y BS"""
    
    list_display = [
        'image_preview', 'code', 'name', 
        'price_usd_display',
        'price_bs_display',
        'unit', 'is_service_badge', 'is_active'
    ]
    list_filter = ['is_active', 'unit', 'is_service']
    search_fields = ['name', 'code', 'description']
    
    fieldsets = (
        ('Información', {
            'fields': ('name', 'code', 'description', 'unit')
        }),
        ('Tipo de Producto', {
            'fields': ('is_service',),
        }),
        ('Precio en USD (Moneda Base)', {
            'fields': ('price',),
            'description': 'Precio en dólares americanos (USD)'
        }),
        ('Características', {
            'fields': ('weight', 'dimensions', 'image')
        }),
        ('Estado', {
            'fields': ('is_active',)
        }),
    )
    
    readonly_fields = ['created_at', 'updated_at', 'price_bs_info']
    
    @admin.display(description='Precio (USD)')
    def price_usd_display(self, obj):
        return f"$ {obj.price:.2f}"
    
    @admin.display(description='Precio (Bs.)')
    def price_bs_display(self, obj):
        try:
            rate = ExchangeRate.get_today_rate('USD', 'BS')
            if rate:
                price_bs = obj.price * rate
                return f"Bs. {price_bs:.2f}"
            return "Sin tasa"
        except:
            return "Error"
    
    @admin.display(description='Precio en Bs. (hoy)')
    def price_bs_info(self, obj):
        try:
            rate = ExchangeRate.get_today_rate('USD', 'BS')
            if not rate:
                return "No hay tasa configurada"
            
            price_bs = obj.price * rate
            local = Currency.objects.get(code='BS')
            
            return format_html(
                '<div style="padding: 10px; background: #f8f9fa; border-radius: 4px;">'
                '<strong>{}</strong><br>'
                'Tasa del día: 1 USD = {} {}<br>'
                'Precio: {} {:.2f}'
                '</div>',
                obj.name,
                rate,
                local.symbol,
                local.symbol,
                price_bs
            )
        except Exception as e:
            return f"Error: {str(e)}"
    
    @admin.display(description='Tipo')
    def is_service_badge(self, obj):
        if obj.is_service:
            return "🛋️ Servicio"
        return "📦 Producto"
    
    @admin.display(description='Imagen')
    def image_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" width="50" height="50" style="object-fit: cover; border-radius: 4px;" />',
                obj.image.url
            )
        return "Sin imagen"


# ============================================================
# ADMIN: UBICACIONES (ANTIGUO WAREHOUSE)
# ============================================================

@admin.register(Location)
class LocationAdmin(CompanyFilterMixin, UnfoldModelAdmin, SimpleHistoryAdmin):
    """Admin de ubicaciones - FILTRADO Y ASIGNACIÓN POR COMPAÑÍA"""
    
    list_display = [
        'code', 
        'name', 
        'company_display',
        'parent', 
        'is_active'
    ]
    
    list_filter = ['is_active', 'company']
    search_fields = ['code', 'name', 'company__name', 'company__code']
    ordering = ['company__code', 'code']
    
    fieldsets = (
        ('Información de la Ubicación', {
            'fields': ('code', 'name', 'description', 'parent')
        }),
        ('Compañía', {
            'fields': ('company',),
            'description': 'Esta ubicación pertenece a una compañía específica'
        }),
        ('Estado', {
            'fields': ('is_active',)
        }),
    )
    
    readonly_fields = ['created_at', 'updated_at']
    
    @admin.display(description='Compañía', ordering='company__name')
    def company_display(self, obj):
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
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        company = getattr(request, 'current_company', None)
        if company:
            return qs.filter(company=company)
        return qs.none()
    
    def save_model(self, request, obj, form, change):
        company = getattr(request, 'current_company', None)
        if not company and request.session.get('active_company_id'):
            try:
                company = Company.objects.get(
                    id=request.session['active_company_id'],
                    is_active=True
                )
            except Company.DoesNotExist:
                pass
        
        if not company:
            company = Company.get_main_company()
        
        if company and hasattr(obj, 'company'):
            obj.company = company
        
        super().save_model(request, obj, form, change)
    
    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if obj is None:
            company = getattr(request, 'current_company', None)
            if company:
                form.base_fields['company'].initial = company.id
        return form
    
    def has_delete_permission(self, request, obj=None):
        if obj:
            from .models import Inventory
            if Inventory.objects.filter(location=obj).exists():
                return False
        return super().has_delete_permission(request, obj)


# ============================================================
# ADMIN: MOVIMIENTOS (ANTIGUO WAREHOUSE)
# ============================================================

@admin.register(Movement)
class MovementAdmin(CompanyFilterMixin, UnfoldModelAdmin, SimpleHistoryAdmin):
    """Admin de movimientos"""
    
    list_display = [
        'product',
        'company',
        'type', 
        'quantity', 
        'unit_price_usd_display',
        'unit_price_bs_display',
        'total_usd_display',
        'total_bs_display',
        'location_from', 
        'location_to', 
        'created_at'
    ]
    list_filter = ['type', 'source_type', 'company']
    search_fields = ['product__name', 'product__code', 'source_reference']
    readonly_fields = ['total', 'user', 'created_at']
    autocomplete_fields = ['product']
    
    fieldsets = (
        ('Movimiento', {
            'fields': ('product', 'type', 'quantity', 'unit_price')
        }),
        ('Ubicaciones', {
            'fields': ('location_from', 'location_to'),
            'description': 'Para entradas solo se usa "Hasta". Para salidas solo "Desde". Para traslados ambos.'
        }),
        ('Información Adicional', {
            'fields': ('source_type', 'source_reference', 'note')
        }),
    )
    
    def has_delete_permission(self, request, obj=None):
        return False
    
    def save_model(self, request, obj, form, change):
        if not obj.user:
            obj.user = request.user
        super().save_model(request, obj, form, change)

    @admin.display(description='Precio (USD)')
    def unit_price_usd_display(self, obj):
        return f"$ {obj.unit_price:.2f}"
    
    @admin.display(description='Precio (Bs.)')
    def unit_price_bs_display(self, obj):
        try:
            rate = ExchangeRate.get_today_rate('USD', 'BS')
            if rate:
                price_bs = obj.unit_price * rate
                return f"Bs. {price_bs:.2f}"
            return "Sin tasa"
        except Exception as e:
            return f"Error: {str(e)}"
    
    @admin.display(description='Total (USD)')
    def total_usd_display(self, obj):
        return f"$ {obj.total:.2f}"
    
    @admin.display(description='Total (Bs.)')
    def total_bs_display(self, obj):
        try:
            rate = ExchangeRate.get_today_rate('USD', 'BS')
            if rate:
                total_bs = obj.total * rate
                return f"Bs. {total_bs:.2f}"
            return "Sin tasa"
        except:
            return "Error"


# ============================================================
# ADMIN: INVENTARIO CONTABLE
# ============================================================

@admin.register(Inventory)
class InventoryAdmin(CompanyFilterMixin, UnfoldModelAdmin):
    list_display = [
        'product',
        'location',
        'company_display',
        'quantity',
        'total_value_usd_display',
        'total_value_bs_display',
        'updated_at'
    ]
    list_filter = ['company', 'location']
    search_fields = ['product__name', 'product__code', 'company__name', 'company__code']
    readonly_fields = ['updated_at']

    @admin.display(description='Compañía', ordering='company__name')
    def company_display(self, obj):
        if obj.company:
            return format_html(
                '<span style="font-weight: 500;">{} - {}</span>',
                obj.company.code,
                obj.company.name
            )
        return "Sin compañía"

    @admin.display(description='Valor total (USD)')
    def total_value_usd_display(self, obj):
        return f"$ {obj.total_value:,.2f}"

    @admin.display(description='Valor total (Bs.)')
    def total_value_bs_display(self, obj):
        try:
            rate = ExchangeRate.get_today_rate('USD', 'BS')
            if rate:
                value_bs = obj.total_value * rate
                return f"Bs. {value_bs:,.2f}"
            return "Sin tasa"
        except Exception:
            return "Error"


@admin.register(ValuationMethod)
class ValuationMethodAdmin(CompanyFilterMixin, UnfoldModelAdmin):
    list_display = ['product', 'company', 'method', 'standard_cost']
    list_filter = ['company', 'method']
    search_fields = ['product__name', 'company__name']


@admin.register(PhysicalCount)
class PhysicalCountAdmin(CompanyFilterMixin, UnfoldModelAdmin):
    list_display = ['product', 'location', 'company', 'count_date', 'counted_quantity', 'system_quantity', 'difference', 'status']
    list_filter = ['company', 'status', 'count_date']
    search_fields = ['product__name', 'company__name']
    readonly_fields = ['difference', 'user', 'created_at']
    
    def save_model(self, request, obj, form, change):
        if not obj.user:
            obj.user = request.user
        obj.system_quantity = InventoryService.get_stock_by_location(obj.product.id, obj.location.id)
        super().save_model(request, obj, form, change)


class DeliveryNoteLineInline(UnfoldTabularInline):
    model = DeliveryNoteLine
    extra = 0
    fields = ['product', 'location', 'quantity']
    autocomplete_fields = ['product', 'location']

    def get_formset(self, request, obj=None, **kwargs):
        formset = super().get_formset(request, obj, **kwargs)
        from .models import Product, Location
        formset.form.base_fields['product'].queryset = Product.objects.filter(is_active=True)
        formset.form.base_fields['location'].queryset = Location.objects.filter(is_active=True)
        return formset

class ReceiptNoteLineInline(UnfoldTabularInline):
    model = ReceiptNoteLine
    extra = 0
    fields = ['product', 'location', 'quantity']
    autocomplete_fields = ['product', 'location']

    def get_formset(self, request, obj=None, **kwargs):
        formset = super().get_formset(request, obj, **kwargs)
        from .models import Product, Location
        formset.form.base_fields['product'].queryset = Product.objects.filter(is_active=True)
        formset.form.base_fields['location'].queryset = Location.objects.filter(is_active=True)
        return formset

# ============================================================
# ADMIN: NOTAS DE ENTREGA
# ============================================================

@admin.action(description='✅ Confirmar notas de entrega seleccionadas')
def confirm_delivery_notes(modeladmin, request, queryset):
    from .services import InventoryService
    for note in queryset:
        try:
            InventoryService.confirm_delivery_note(note.id, request.user)
            modeladmin.message_user(request, f'✅ Nota {note.number} confirmada exitosamente', messages.SUCCESS)
        except Exception as e:
            modeladmin.message_user(request, f'❌ Error en {note.number}: {str(e)}', messages.ERROR)

@admin.action(description='❌ Cancelar notas de entrega seleccionadas')
def cancel_delivery_notes(modeladmin, request, queryset):
    from .services import InventoryService
    for note in queryset:
        try:
            InventoryService.cancel_delivery_note(note.id, request.user)
            modeladmin.message_user(request, f'✅ Nota {note.number} cancelada', messages.SUCCESS)
        except Exception as e:
            modeladmin.message_user(request, f'❌ Error en {note.number}: {str(e)}', messages.ERROR)

@admin.register(DeliveryNote)
class DeliveryNoteAdmin(CompanyFilterMixin, UnfoldModelAdmin):
    list_display = ['number', 'customer_name', 'customer', 'date', 'status', 'company']
    list_filter = ['status', 'date', 'company']
    search_fields = ['number', 'customer_name', 'customer__name']
    inlines = [DeliveryNoteLineInline]
    actions = [confirm_delivery_notes, cancel_delivery_notes]
    
    fieldsets = (
        ('Información', {
            'fields': ('number', 'customer', 'customer_name')
        }),
        ('Detalles', {
            'fields': ('notes', 'status')
        }),
    )
    readonly_fields = ['number', 'date', 'user', 'created_at', 'updated_at']
    
    def save_model(self, request, obj, form, change):
        if not obj.user:
            obj.user = request.user
        if not obj.company_id:
            company = getattr(request, 'current_company', None)
            if company:
                obj.company = company
        super().save_model(request, obj, form, change)

# ============================================================
# ADMIN: NOTAS DE RECIBO
# ============================================================

@admin.action(description='✅ Confirmar notas de recibo seleccionadas')
def confirm_receipt_notes(modeladmin, request, queryset):
    from .services import InventoryService
    for note in queryset:
        try:
            InventoryService.confirm_receipt_note(note.id, request.user)
            modeladmin.message_user(request, f'✅ Nota {note.number} confirmada exitosamente', messages.SUCCESS)
        except Exception as e:
            modeladmin.message_user(request, f'❌ Error en {note.number}: {str(e)}', messages.ERROR)

@admin.action(description='❌ Cancelar notas de recibo seleccionadas')
def cancel_receipt_notes(modeladmin, request, queryset):
    from .services import InventoryService
    for note in queryset:
        try:
            InventoryService.cancel_receipt_note(note.id, request.user)
            modeladmin.message_user(request, f'✅ Nota {note.number} cancelada', messages.SUCCESS)
        except Exception as e:
            modeladmin.message_user(request, f'❌ Error en {note.number}: {str(e)}', messages.ERROR)

@admin.register(ReceiptNote)
class ReceiptNoteAdmin(CompanyFilterMixin, UnfoldModelAdmin):
    list_display = ['number', 'supplier_name', 'supplier', 'date', 'status', 'company']
    list_filter = ['status', 'date', 'company']
    search_fields = ['number', 'supplier_name', 'supplier__name']
    inlines = [ReceiptNoteLineInline]
    actions = [confirm_receipt_notes, cancel_receipt_notes]
    
    fieldsets = (
        ('Información', {
            'fields': ('number', 'supplier', 'supplier_name')
        }),
        ('Detalles', {
            'fields': ('notes', 'status')
        }),
    )
    readonly_fields = ['number', 'date', 'user', 'created_at', 'updated_at']
    
    def save_model(self, request, obj, form, change):
        if not obj.user:
            obj.user = request.user
        if not obj.company_id:
            company = getattr(request, 'current_company', None)
            if company:
                obj.company = company
        super().save_model(request, obj, form, change)