# django_erp/accounting/admin.py
from django.contrib import admin
from unfold.admin import ModelAdmin as UnfoldModelAdmin
from unfold.admin import TabularInline as UnfoldTabularInline
from simple_history.admin import SimpleHistoryAdmin

from .models import Tax, TaxRate


@admin.register(Tax)
class TaxAdmin(UnfoldModelAdmin, SimpleHistoryAdmin):
    list_display = ['code', 'name', 'tax_type', 'is_active']
    list_filter = ['tax_type', 'is_active']
    search_fields = ['code', 'name']
    
    fieldsets = (
        ('Información del Impuesto', {
            'fields': ('code', 'name', 'description')
        }),
        ('Configuración', {
            'fields': ('tax_type', 'is_active')
        }),
    )


@admin.register(TaxRate)
class TaxRateAdmin(UnfoldModelAdmin, SimpleHistoryAdmin):
    list_display = ['tax', 'company', 'rate_percent', 'effective_date', 'is_default_badge', 'is_active']
    list_filter = ['tax', 'company', 'is_default', 'effective_date']
    search_fields = ['tax__code', 'tax__name', 'company__name', 'company__code']
    autocomplete_fields = ['tax', 'company']
    
    fieldsets = (
        ('Impuesto y Compañía', {
            'fields': ('tax', 'company')
        }),
        ('Tasa de Impuesto', {
            'fields': ('rate', 'effective_date', 'is_default')
        }),
        ('Información Adicional', {
            'fields': ('note',)
        }),
    )
    
    @admin.display(description='Tasa', ordering='rate')
    def rate_percent(self, obj):
        return f"{obj.rate}%"
    
    @admin.display(description='Por Defecto', boolean=True)
    def is_default_badge(self, obj):
        return obj.is_default
    
    @admin.display(description='Vigente', boolean=True)
    def is_active(self, obj):
        # Considerar activa si la fecha de vigencia es <= hoy
        from datetime import date
        return obj.effective_date <= date.today()