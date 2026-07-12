# warehouse/admin.py
from django.contrib import admin
from django.utils.html import format_html
from simple_history.admin import SimpleHistoryAdmin
from unfold.admin import ModelAdmin as UnfoldModelAdmin
from .models import Product, Location, Movement
from django_erp.configuration.services import CurrencyService


@admin.register(Product)
class ProductAdmin(SimpleHistoryAdmin, UnfoldModelAdmin):
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
        ('Precio en Bolívares', {
            'fields': ('price_bs_info',),
            'description': 'Precio convertido a Bolívares según tasa del día'
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
class LocationAdmin(UnfoldModelAdmin, SimpleHistoryAdmin):
    """Admin de ubicaciones"""
    
    list_display = ['code', 'name', 'parent', 'is_active']
    list_filter = ['is_active']
    search_fields = ['code', 'name']


@admin.register(Movement)
class MovementAdmin(UnfoldModelAdmin, SimpleHistoryAdmin):
    """Admin de movimientos"""
    
    list_display = ['product', 'type', 'quantity', 'unit_price', 'total', 'location_from', 'location_to', 'created_at']
    list_filter = ['type', 'source_type']
    search_fields = ['product__name', 'product__code', 'source_reference']
    readonly_fields = ['total', 'user', 'created_at']
    
    fieldsets = (
        ('Movimiento', {
            'fields': ('product', 'type', 'quantity')
        }),
        ('Precios', {
            'fields': ('unit_price', 'total'),
            'description': 'El total se calcula automáticamente: Cantidad × Precio unitario'
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