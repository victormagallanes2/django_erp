# warehouse/admin.py
from django.contrib import admin
from django.utils.html import format_html
from unfold.admin import ModelAdmin as UnfoldModelAdmin
from .models import Product, Location, Movement


@admin.register(Product)
class ProductAdmin(UnfoldModelAdmin):
    list_display = ['image_preview', 'code', 'name', 'unit', 'is_active']
    list_filter = ['is_active', 'unit']
    search_fields = ['name', 'code']
    fieldsets = (
        ('Información', {'fields': ('name', 'code', 'description', 'unit', 'image')}),
        ('Características', {'fields': ('weight', 'dimensions')}),
        ('Estado', {'fields': ('is_active',)}),
        ('Precios', {
            'fields': ('unit_price', 'total'),
            'description': 'El total se calcula automáticamente: Cantidad × Precio unitario'
        }),
    )
    readonly_fields = ['created_at', 'updated_at']
    
    @admin.display(description='Imagen')
    def image_preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" width="50" height="50" style="object-fit: cover; border-radius: 4px;" />', obj.image.url)
        return "Sin imagen"


@admin.register(Location)
class LocationAdmin(UnfoldModelAdmin):
    list_display = ['code', 'name', 'parent', 'is_active']
    list_filter = ['is_active']
    search_fields = ['code', 'name']


@admin.register(Movement)
class MovementAdmin(UnfoldModelAdmin):
    list_display = ['product', 'type', 'quantity', 'unit_price', 'total', 'location_from', 'location_to', 'created_at']
    list_filter = ['type', 'source_type']
    search_fields = ['product__name', 'source_reference']
    readonly_fields = ['user', 'created_at', 'total']
    
    def has_delete_permission(self, request, obj=None):
        return False
    
    def save_model(self, request, obj, form, change):
        if not obj.user:
            obj.user = request.user
        super().save_model(request, obj, form, change)
