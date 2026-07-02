# inventory/admin.py
from django.contrib import admin
from unfold.admin import ModelAdmin as UnfoldModelAdmin
from .models import Inventory, ValuationMethod, PhysicalCount
from .services import InventoryService


@admin.register(Inventory)
class InventoryAdmin(UnfoldModelAdmin):
    list_display = ['product', 'location', 'quantity', 'total_value', 'updated_at']
    list_filter = ['location']
    search_fields = ['product__name', 'product__code']
    readonly_fields = ['updated_at']


@admin.register(ValuationMethod)
class ValuationMethodAdmin(UnfoldModelAdmin):
    list_display = ['product', 'method', 'standard_cost']
    search_fields = ['product__name']


@admin.register(PhysicalCount)
class PhysicalCountAdmin(UnfoldModelAdmin):
    list_display = ['product', 'location', 'count_date', 'counted_quantity', 'system_quantity', 'difference', 'status']
    list_filter = ['status', 'count_date']
    search_fields = ['product__name']
    readonly_fields = ['difference', 'user', 'created_at']
    
    def save_model(self, request, obj, form, change):
        if not obj.user:
            obj.user = request.user
        # Obtener cantidad del sistema desde InventoryService
        obj.system_quantity = InventoryService.get_stock_by_location(obj.product.id, obj.location.id)
        super().save_model(request, obj, form, change)
