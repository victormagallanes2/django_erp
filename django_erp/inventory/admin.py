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
from django_erp.configuration.models import ExchangeRate, Currency, Company
from django_erp.configuration.mixins import CompanyFilterMixin
from .services import InventoryService
from .models import DeliveryNote, DeliveryNoteLine, ReceiptNote, ReceiptNoteLine
from django.contrib import messages
from django.core.exceptions import ValidationError
import logging

logger = logging.getLogger(__name__)


# ============================================================
# ADMIN: PRODUCTOS
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
# ADMIN: UBICACIONES
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
# ADMIN: MOVIMIENTOS
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

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.select_related('product')


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
    """Admin de Notas de Entrega - CON LÓGICA DE CONFIRMACIÓN"""
    
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
        """
        ✅ Guardar la nota de entrega.
        Si se confirma, ejecutar la lógica de negocio.
        """
        logger.info("=" * 80)
        logger.info("🔴 [DeliveryNoteAdmin.save_model] INICIANDO")
        logger.info(f"   Nota: {obj.number}")
        logger.info(f"   Estado en formulario: {obj.status}")
        logger.info(f"   Change: {change}")
        logger.info(f"   PK: {obj.pk}")
        
        # ✅ Asignar usuario y compañía
        if not obj.user:
            obj.user = request.user
            logger.info("   ✅ Usuario asignado")
        
        if not obj.company_id:
            company = getattr(request, 'current_company', None)
            if company:
                obj.company = company
                logger.info(f"   ✅ Compañía asignada: {company.code}")
        
        # ✅ Obtener el estado anterior si existe
        old_status = None
        new_status = obj.status
        
        if change and obj.pk:
            try:
                old_note = DeliveryNote.objects.get(pk=obj.pk)
                old_status = old_note.status
                logger.info(f"   Estado anterior en BD: {old_status}")
            except DeliveryNote.DoesNotExist:
                logger.warning("   ⚠️ Nota no encontrada en BD")
        
        logger.info(f"   Nuevo estado solicitado: {new_status}")
        
        # ✅ Si el estado cambió a CONFIRMED, ejecutar la lógica de negocio
        if old_status != 'CONFIRMED' and new_status == 'CONFIRMED':
            logger.info(f"   🎯 Nota {obj.number} cambiando a CONFIRMED - Ejecutando lógica de negocio")
            
            try:
                # ✅ IMPORTANTE: El servicio espera que la nota esté en DRAFT
                obj.status = 'DRAFT'
                logger.info("   ⚠️ Estado temporalmente cambiado a DRAFT para el servicio")
                
                # ✅ Llamar al servicio para confirmar la nota
                result = InventoryService.confirm_delivery_note(obj.id, request.user)
                logger.info(f"   ✅ Nota {obj.number} confirmada exitosamente por el servicio")
                
                # ✅ Recargar el objeto para obtener los cambios del servicio
                obj.refresh_from_db()
                logger.info(f"   Estado después del servicio: {obj.status}")
                
                self.message_user(
                    request,
                    f'✅ Nota de entrega {obj.number} confirmada exitosamente',
                    messages.SUCCESS
                )
                
                # ✅ No llamar a super().save_model() porque el servicio ya guardó
                return
                
            except Exception as e:
                logger.error(f"   ❌ Error confirmando nota: {e}")
                import traceback
                logger.error(f"   Traceback: {traceback.format_exc()}")
                
                # ✅ Revertir el estado a DRAFT
                obj.status = 'DRAFT'
                self.message_user(
                    request,
                    f'❌ Error al confirmar nota {obj.number}: {str(e)}',
                    messages.ERROR
                )
                # Guardar con estado DRAFT para no perder los cambios
                super().save_model(request, obj, form, change)
                return
        
        # ✅ Si no hay cambio a CONFIRMED, guardar normalmente
        logger.info("   ℹ️ Guardando nota sin lógica de negocio especial")
        super().save_model(request, obj, form, change)
        logger.info("   ✅ Nota guardada normalmente")
        
        logger.info("🔴 [DeliveryNoteAdmin.save_model] FINALIZADO")
        logger.info("=" * 80)
    
    def save_formset(self, request, form, formset, change):
        """
        Guardar las líneas de la nota de entrega.
        """
        logger.info("🔴 [DeliveryNoteAdmin.save_formset] INICIANDO")
        
        company = getattr(request, 'current_company', None)
        if not company:
            company = Company.get_active()
        
        logger.info(f"   Compañía para líneas: {company.code if company else 'N/A'}")
        
        instances = formset.save(commit=False)
        logger.info(f"   Instancias a guardar: {len(instances)}")
        
        for instance in instances:
            if hasattr(instance, 'company') and not instance.company_id:
                instance.company = company
                logger.info(f"   ✅ Compañía asignada a línea: {company.code if company else 'N/A'}")
            instance.save()
            logger.info(f"   ✅ Línea guardada: {instance}")
        
        formset.save_m2m()
        
        for obj in formset.deleted_objects:
            logger.info(f"   🗑️ Eliminando objeto: {obj}")
            obj.delete()
        
        logger.info("🔴 [DeliveryNoteAdmin.save_formset] FINALIZADO")
        return super().save_formset(request, form, formset, change)


# ============================================================
# ADMIN: NOTAS DE RECIBO - CORREGIDO (VERSIÓN FINAL)
# ============================================================

@admin.action(description='✅ Confirmar notas de recibo seleccionadas')
def confirm_receipt_notes(modeladmin, request, queryset):
    """Acción masiva para confirmar notas de recibo"""
    logger.info("=" * 80)
    logger.info("🔴 [confirm_receipt_notes] ACCIÓN MASIVA DISPARADA")
    logger.info(f"   Notas a confirmar: {queryset.count()}")
    
    for note in queryset:
        try:
            logger.info(f"   📝 Confirmando nota {note.number}")
            InventoryService.confirm_receipt_note(note.id, request.user)
            modeladmin.message_user(
                request, 
                f'✅ Nota {note.number} confirmada exitosamente', 
                messages.SUCCESS
            )
            logger.info(f"   ✅ Nota {note.number} confirmada exitosamente")
        except Exception as e:
            logger.error(f"   ❌ Error en {note.number}: {str(e)}")
            import traceback
            logger.error(f"   Traceback: {traceback.format_exc()}")
            modeladmin.message_user(
                request, 
                f'❌ Error en {note.number}: {str(e)}', 
                messages.ERROR
            )
    
    logger.info("=" * 80)

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
    """Admin de Notas de Recibo - CON LÓGICA DE CONFIRMACIÓN"""
    
    list_display = ['number', 'supplier_name', 'supplier', 'purchase_order', 'date', 'status', 'company']
    list_filter = ['status', 'date', 'company']
    search_fields = ['number', 'supplier_name', 'supplier__name', 'purchase_order__number']
    inlines = [ReceiptNoteLineInline]
    actions = [confirm_receipt_notes, cancel_receipt_notes]
    
    fieldsets = (
        ('Información', {
            'fields': ('number', 'purchase_order', 'supplier', 'supplier_name')
        }),
        ('Detalles', {
            'fields': ('notes', 'status')
        }),
    )
    readonly_fields = ['number', 'date', 'purchase_order', 'user', 'created_at', 'updated_at']
    
    def save_model(self, request, obj, form, change):
        """
        ✅ CORREGIDO: Cuando se confirma una nota de recibo desde el admin,
        se ejecuta la lógica de negocio.
        
        IMPORTANTE: El servicio confirm_receipt_note espera que la nota esté
        en estado DRAFT. Por eso, llamamos al servicio ANTES de guardar
        el objeto, y dejamos que el servicio maneje el cambio de estado.
        """
        logger.info("=" * 80)
        logger.info("🔴 [ReceiptNoteAdmin.save_model] INICIANDO")
        logger.info(f"   Nota: {obj.number}")
        logger.info(f"   Estado en formulario: {obj.status}")
        logger.info(f"   Change: {change}")
        logger.info(f"   PK: {obj.pk}")
        
        # ✅ Asignar usuario y compañía (sin guardar aún)
        if not obj.user:
            obj.user = request.user
            logger.info("   ✅ Usuario asignado")
        
        if not obj.company_id:
            company = getattr(request, 'current_company', None)
            if company:
                obj.company = company
                logger.info(f"   ✅ Compañía asignada: {company.code}")
        
        # ✅ Obtener el estado anterior si existe
        old_status = None
        new_status = obj.status
        
        if change and obj.pk:
            try:
                old_note = ReceiptNote.objects.get(pk=obj.pk)
                old_status = old_note.status
                logger.info(f"   Estado anterior en BD: {old_status}")
            except ReceiptNote.DoesNotExist:
                logger.warning("   ⚠️ Nota no encontrada en BD")
        
        logger.info(f"   Nuevo estado solicitado: {new_status}")
        
        # ✅ Si el estado cambió a CONFIRMED, ejecutar la lógica de negocio
        if old_status != 'CONFIRMED' and new_status == 'CONFIRMED':
            logger.info(f"   🎯 Nota {obj.number} cambiando a CONFIRMED - Ejecutando lógica de negocio")
            
            try:
                # ✅ IMPORTANTE: El servicio espera que la nota esté en DRAFT
                # Pero como el formulario ya tiene CONFIRMED, debemos temporalmente
                # cambiar el estado a DRAFT antes de llamar al servicio
                obj.status = 'DRAFT'
                logger.info("   ⚠️ Estado temporalmente cambiado a DRAFT para el servicio")
                
                # ✅ Llamar al servicio para confirmar la nota
                # El servicio cambiará el estado a CONFIRMED y creará los movimientos
                result = InventoryService.confirm_receipt_note(obj.id, request.user)
                logger.info(f"   ✅ Nota {obj.number} confirmada exitosamente por el servicio")
                
                # ✅ Recargar el objeto para obtener los cambios del servicio
                obj.refresh_from_db()
                logger.info(f"   Estado después del servicio: {obj.status}")
                
                self.message_user(
                    request,
                    f'✅ Nota de recibo {obj.number} confirmada exitosamente',
                    messages.SUCCESS
                )
                
                # ✅ No llamar a super().save_model() porque el servicio ya guardó
                return
                
            except Exception as e:
                logger.error(f"   ❌ Error confirmando nota: {e}")
                import traceback
                logger.error(f"   Traceback: {traceback.format_exc()}")
                
                # ✅ Revertir el estado a DRAFT
                obj.status = 'DRAFT'
                self.message_user(
                    request,
                    f'❌ Error al confirmar nota {obj.number}: {str(e)}',
                    messages.ERROR
                )
                # Guardar con estado DRAFT para no perder los cambios
                super().save_model(request, obj, form, change)
                return
        
        # ✅ Si no hay cambio a CONFIRMED, guardar normalmente
        logger.info("   ℹ️ Guardando nota sin lógica de negocio especial")
        super().save_model(request, obj, form, change)
        logger.info("   ✅ Nota guardada normalmente")
        
        logger.info("🔴 [ReceiptNoteAdmin.save_model] FINALIZADO")
        logger.info("=" * 80)
    
    def save_formset(self, request, form, formset, change):
        """
        Guardar las líneas de la nota de recibo.
        """
        logger.info("🔴 [ReceiptNoteAdmin.save_formset] INICIANDO")
        
        # ✅ Obtener la compañía activa
        company = getattr(request, 'current_company', None)
        if not company:
            company = Company.get_active()
        
        logger.info(f"   Compañía para líneas: {company.code if company else 'N/A'}")
        
        # ✅ Guardar las instancias del formset
        instances = formset.save(commit=False)
        logger.info(f"   Instancias a guardar: {len(instances)}")
        
        for instance in instances:
            if hasattr(instance, 'company') and not instance.company_id:
                instance.company = company
                logger.info(f"   ✅ Compañía asignada a línea: {company.code if company else 'N/A'}")
            instance.save()
            logger.info(f"   ✅ Línea guardada: {instance}")
        
        # ✅ Guardar relaciones ManyToMany
        formset.save_m2m()
        
        # ✅ Eliminar objetos marcados para borrar
        for obj in formset.deleted_objects:
            logger.info(f"   🗑️ Eliminando objeto: {obj}")
            obj.delete()
        
        logger.info("🔴 [ReceiptNoteAdmin.save_formset] FINALIZADO")
        return super().save_formset(request, form, formset, change)


@admin.action(description='✅ Confirmar notas de entrega seleccionadas')
def confirm_delivery_notes(modeladmin, request, queryset):
    """Acción masiva para confirmar notas de entrega"""
    from .services import InventoryService
    
    logger.info("=" * 80)
    logger.info("🔴 [confirm_delivery_notes] ACCIÓN MASIVA DISPARADA")
    logger.info(f"   Notas a confirmar: {queryset.count()}")
    
    for note in queryset:
        try:
            logger.info(f"   📝 Confirmando nota {note.number}")
            InventoryService.confirm_delivery_note(note.id, request.user)
            modeladmin.message_user(
                request, 
                f'✅ Nota {note.number} confirmada exitosamente', 
                messages.SUCCESS
            )
            logger.info(f"   ✅ Nota {note.number} confirmada exitosamente")
        except Exception as e:
            logger.error(f"   ❌ Error en {note.number}: {str(e)}")
            import traceback
            logger.error(f"   Traceback: {traceback.format_exc()}")
            modeladmin.message_user(
                request, 
                f'❌ Error en {note.number}: {str(e)}', 
                messages.ERROR
            )
    
    logger.info("=" * 80)

