# inventory/admin.py
from django.contrib import admin
from django.utils.html import format_html
from unfold.admin import ModelAdmin as UnfoldModelAdmin
from .models import Inventory, ValuationMethod, PhysicalCount
from .services import InventoryService
from django_erp.configuration.models import ExchangeRate
from django_erp.configuration.mixins import CompanyFilterMixin


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

    # ✅ Campo: Total en USD
    @admin.display(description='Valor total (USD)')
    def total_value_usd_display(self, obj):
        return f"$ {obj.total_value:,.2f}"

    # ✅ Campo: Total en Bs. (convertido)
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
        # Obtener cantidad del sistema desde InventoryService
        obj.system_quantity = InventoryService.get_stock_by_location(obj.product.id, obj.location.id)
        super().save_model(request, obj, form, change)
