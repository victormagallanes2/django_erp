# warehouse/admin.py
from django.contrib import admin
from django.utils.html import format_html
from unfold.admin import ModelAdmin as UnfoldModelAdmin
from .models import Product, Location, Movement


@admin.register(Product)
class ProductAdmin(UnfoldModelAdmin):
    list_display = [
        'image_preview', 'code', 'name', 'sale_price', 'unit', 
        'is_service_badge', 'is_active'
    ]
    list_filter = ['is_active', 'unit', 'is_service']
    search_fields = ['name', 'code', 'description']
    
    fieldsets = (
        ('Información', {
            'fields': ('name', 'code', 'description', 'unit')
        }),
        ('Tipo de Producto', {
            'fields': ('is_service',),
            'description': 'Marcar como "Servicio" si no requiere control de stock'
        }),
        ('Precios', {
            'fields': ('sale_price',)
        }),
        ('Características', {
            'fields': ('weight', 'dimensions')
        }),
        ('Imagen', {
            'fields': ('image',)
        }),
        ('Estado', {
            'fields': ('is_active',)
        }),
    )
    
    readonly_fields = ['created_at', 'updated_at']

    def has_view_permission(self, request, obj=None):
        return request.user.has_perm('warehouse.view_product')
    
    def has_add_permission(self, request):
        return request.user.has_perm('warehouse.add_product')
    
    def has_change_permission(self, request, obj=None):
        return request.user.has_perm('warehouse.change_product')
    
    def has_delete_permission(self, request, obj=None):
        return request.user.has_perm('warehouse.delete_product')
    
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
class LocationAdmin(UnfoldModelAdmin):
    """Admin de ubicaciones"""
    
    list_display = ['code', 'name', 'parent', 'is_active']
    list_filter = ['is_active']
    search_fields = ['code', 'name']


@admin.register(Movement)
class MovementAdmin(UnfoldModelAdmin):
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