# warehouse/admin.py
from django.contrib import admin
from django.utils.html import format_html
from simple_history.admin import SimpleHistoryAdmin
from unfold.admin import ModelAdmin as UnfoldModelAdmin
from .models import Product, Location, Movement
from django_erp.configuration.services import CurrencyService
from django_erp.configuration.models import ExchangeRate, Currency
from django_erp.configuration.mixins import CompanyFilterMixin


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
        """Mostrar precio en USD con símbolo"""
        return f"$ {obj.price:.2f}"
    
    @admin.display(description='Precio (Bs.)')
    def price_bs_display(self, obj):
        """Mostrar precio en Bolívares con símbolo"""
        try:
            from django_erp.configuration.models import ExchangeRate
            
            # ✅ Obtener tasa del día
            rate = ExchangeRate.get_today_rate('USD', 'BS')
            if rate:
                price_bs = obj.price * rate
                return f"Bs. {price_bs:.2f}"
            return "Sin tasa"
        except:
            return "Error"
    
    @admin.display(description='Precio en Bs. (hoy)')
    def price_bs_info(self, obj):
        """Mostrar precio en Bolívares con tasa actual"""
        try:
            from django_erp.configuration.models import ExchangeRate
            from django_erp.configuration.models import Currency
            
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


@admin.register(Location)
class LocationAdmin(CompanyFilterMixin, UnfoldModelAdmin, SimpleHistoryAdmin):
    """
    Admin de ubicaciones - FILTRADO Y ASIGNACIÓN POR COMPAÑÍA
    """
    
    # ✅ Listado con compañía visible
    list_display = [
        'code', 
        'name', 
        'company_display',  # ← Mostrar compañía
        'parent', 
        'is_active'
    ]
    
    # ✅ Filtros incluyendo compañía
    list_filter = ['is_active', 'company']
    
    # ✅ Búsqueda incluyendo compañía
    search_fields = ['code', 'name', 'company__name', 'company__code']
    
    # ✅ Ordenación por compañía y código
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
    
    # ✅ Método para mostrar la compañía con formato
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
    
    # ✅ Sobrescribir get_queryset para filtrar por compañía
    def get_queryset(self, request):
        """
        Mostrar solo ubicaciones de la compañía actual.
        Los superusuarios ven todas las compañías.
        """
        qs = super().get_queryset(request)
        
        # ✅ Si es superusuario, ver todo
        if request.user.is_superuser:
            return qs
        
        # ✅ Si hay compañía activa, filtrar
        company = getattr(request, 'current_company', None)
        if company:
            return qs.filter(company=company)
        
        # ✅ Si no hay compañía activa, no mostrar nada
        return qs.none()
    
    # ✅ Sobrescribir save_model para asignar compañía automáticamente
    def save_model(self, request, obj, form, change):
        """
        Asignar la compañía activa al guardar una ubicación.
        """
        print(f"🔴 ===== LocationAdmin: save_model =====")
        print(f"   Ubicación: {obj.code} - {obj.name}")
        print(f"   Tiene company: {hasattr(obj, 'company')}")
        print(f"   company_id actual: {getattr(obj, 'company_id', 'NO TIENE')}")
        
        # ✅ OBTENER COMPAÑÍA ACTIVA
        company = getattr(request, 'current_company', None)
        
        # ✅ Si no hay compañía en request, obtener de la sesión o la principal
        if not company and request.session.get('active_company_id'):
            try:
                company = Company.objects.get(
                    id=request.session['active_company_id'],
                    is_active=True
                )
                print(f"   Compañía de sesión: {company.code}")
            except Company.DoesNotExist:
                pass
        
        # ✅ Fallback: compañía principal
        if not company:
            from django_erp.configuration.models import Company
            company = Company.get_main_company()
            print(f"   Fallback (compañía principal): {company.code if company else 'None'}")
        
        # ✅ ASIGNAR COMPAÑÍA
        if company and hasattr(obj, 'company'):
            obj.company = company
            print(f"   ✅ Compañía asignada: {company.code} (ID: {company.id})")
        else:
            print(f"   ❌ No se encontró compañía activa para asignar")
        
        print(f"   company_id después de asignar: {obj.company_id}")
        print("🔴 ===== FIN LocationAdmin save_model =====")
        
        super().save_model(request, obj, form, change)
    
    # ✅ Método para asegurar que el formulario muestre la compañía actual
    def get_form(self, request, obj=None, **kwargs):
        """
        Configurar el formulario para mostrar la compañía actual.
        """
        form = super().get_form(request, obj, **kwargs)
        
        # ✅ Si es una nueva ubicación, pre-seleccionar la compañía actual
        if obj is None:
            company = getattr(request, 'current_company', None)
            if company:
                form.base_fields['company'].initial = company.id
                # ✅ Opcional: hacer el campo de solo lectura para que no se pueda cambiar
                # form.base_fields['company'].disabled = True
        
        return form
    
    # ✅ Método para verificar permisos de eliminación
    def has_delete_permission(self, request, obj=None):
        """
        Prevenir eliminación de ubicaciones que tienen inventario.
        """
        if obj:
            # Verificar si tiene inventario asociado
            from django_erp.inventory.models import Inventory
            if Inventory.objects.filter(location=obj).exists():
                return False
        return super().has_delete_permission(request, obj)


@admin.register(Movement)
class MovementAdmin(CompanyFilterMixin, UnfoldModelAdmin, SimpleHistoryAdmin):
    """Admin de movimientos"""
    
    list_display = [
        'product',
        'company',
        'type', 
        'quantity', 
        'unit_price_usd_display',  # ✅ Precio en USD
        'unit_price_bs_display',   # ✅ Precio en Bs.
        'total_usd_display',       # ✅ Total en USD
        'total_bs_display',        # ✅ Total en Bs.
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

    # ✅ Métodos para mostrar precios en USD y Bs.
    @admin.display(description='Precio (USD)')
    def unit_price_usd_display(self, obj):
        """Mostrar precio unitario en USD"""
        return f"$ {obj.unit_price:.2f}"
    
    @admin.display(description='Precio (Bs.)')
    def unit_price_bs_display(self, obj):
        """Mostrar precio unitario en Bs."""
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
        """Mostrar total en USD"""
        return f"$ {obj.total:.2f}"
    
    @admin.display(description='Total (Bs.)')
    def total_bs_display(self, obj):
        """Mostrar total en Bs."""
        try:
            rate = ExchangeRate.get_today_rate('USD', 'BS')
            if rate:
                total_bs = obj.total * rate
                return f"Bs. {total_bs:.2f}"
            return "Sin tasa"
        except:
            return "Error"