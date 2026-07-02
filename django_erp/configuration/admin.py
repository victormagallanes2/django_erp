# configuration/admin.py
from django.contrib import admin
from django.utils.html import format_html
from unfold.admin import ModelAdmin as UnfoldModelAdmin
from .models import Company


@admin.register(Company)
class CompanyAdmin(UnfoldModelAdmin):
    """Configuración de la empresa"""
    
    list_display = ['logo_preview', 'name', 'rif', 'tax_rate', 'currency', 'is_active']
    list_filter = ['is_active', 'currency']
    search_fields = ['name', 'rif']
    
    fieldsets = (
        ('Datos de la Empresa', {
            'fields': ('name', 'trade_name', 'rif', 'logo')
        }),
        ('Contacto', {
            'fields': ('address', 'phone', 'email', 'website')
        }),
        ('Configuración Fiscal', {
            'fields': ('tax_rate', 'currency'),
            'classes': ('tab',),
        }),
        ('Configuración de Facturación', {
            'fields': ('invoice_prefix', 'control_number_required'),
            'classes': ('tab',),
            'description': 'Configuración específica para facturación electrónica'
        }),
        ('Estado', {
            'fields': ('is_active',),
            'classes': ('tab',),
        }),
    )
    
    readonly_fields = ['created_at', 'updated_at']
    
    @admin.display(description='Logo')
    def logo_preview(self, obj):
        if obj.logo:
            return format_html(
                '<img src="{}" width="50" height="50" style="object-fit: contain;" />',
                obj.logo.url
            )
        return "Sin logo"
    
    def has_delete_permission(self, request, obj=None):
        """Prevenir eliminación de la empresa activa"""
        if obj and obj.is_active:
            return False
        return super().has_delete_permission(request, obj)
