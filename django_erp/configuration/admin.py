from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse, path
from django.contrib import messages
from django.shortcuts import redirect
from django.http import FileResponse
from simple_history.admin import SimpleHistoryAdmin
from unfold.admin import ModelAdmin as UnfoldModelAdmin
from .models import Company, Backup, PaymentMethod
from .services import BackupService
from .models import Currency, ExchangeRate
import os


@admin.register(Company)
class CompanyAdmin(UnfoldModelAdmin, SimpleHistoryAdmin):
    list_display = ['logo_preview', 'name', 'rif', 'tax_rate', 'is_active']
    list_filter = ['is_active']
    search_fields = ['name', 'rif']
    
    fieldsets = (
        ('Datos de la Empresa', {
            'fields': ('name', 'trade_name', 'rif', 'logo')
        }),
        ('Contacto', {
            'fields': ('address', 'phone', 'email', 'website')
        }),
        ('Configuración Fiscal', {
            'fields': ('tax_rate',),
            'classes': ('tab',),
        }),
        ('Configuración de Facturación', {
            'fields': ('invoice_prefix', 'control_number_required'),
            'classes': ('tab',),
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
        if obj and obj.is_active:
            return False
        return super().has_delete_permission(request, obj)


@admin.register(Backup)
class BackupAdmin(UnfoldModelAdmin, SimpleHistoryAdmin):
    """Admin de respaldos - Solo crear"""
    
    # ✅ Usar template personalizado
    change_list_template = "admin/configuration/backup_changelist.html"
    
    list_display = ['name', 'file_size_display', 'status_badge', 'created_at', 'user']
    list_filter = ['status', 'created_at']
    search_fields = ['name', 'note']
    readonly_fields = ['created_at', 'completed_at', 'user', 'name', 'file_path', 'status']
    
    fieldsets = (
        ('Información', {
            'fields': ('name', 'status')
        }),
        ('Fechas', {
            'fields': ('created_at', 'completed_at')
        }),
        ('Usuario', {
            'fields': ('user', 'note')
        }),
    )
    
    def has_add_permission(self, request):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False
    
    @admin.display(description='Tamaño')
    def file_size_display(self, obj):
        return obj.file_size_display
    
    @admin.display(description='Estado')
    def status_badge(self, obj):
        colors = {
            'PENDING': ('#ffc107', '⏳ Pendiente'),
            'PROCESSING': ('#17a2b8', '🔄 Procesando'),
            'COMPLETED': ('#28a745', '✅ Completado'),
            'FAILED': ('#dc3545', '❌ Fallido'),
        }
        color, label = colors.get(obj.status, ('#6c757d', obj.status))
        return format_html(
            '<span style="background: {}; color: white; padding: 2px 10px; border-radius: 12px; font-size: 12px;">{}</span>',
            color,
            label
        )
    
    # ✅ Vista para crear desde el botón
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('create/', self.admin_site.admin_view(self.create_backup_view), name='backup_create'),
        ]
        return custom_urls + urls
    
    def create_backup_view(self, request):
        try:
            backup = BackupService.create_backup(user=request.user)
            file_path = backup.file_path
            response = FileResponse(open(file_path, 'rb'))
            response['Content-Disposition'] = f'attachment; filename="{os.path.basename(file_path)}"'
            return response
        except Exception as e:
            self.message_user(request, f'❌ Error: {str(e)}', messages.ERROR)
            return redirect('admin:configuration_backup_changelist')
    
    # ✅ Eliminar acciones del dropdown
    def get_actions(self, request):
        # Retornar diccionario vacío para eliminar todas las acciones
        return {}


@admin.register(Currency)
class CurrencyAdmin(UnfoldModelAdmin, SimpleHistoryAdmin):
    """Admin de monedas"""
    
    list_display = ['code', 'name', 'symbol', 'is_base_badge', 'is_active']
    list_filter = ['is_active', 'is_base']
    search_fields = ['code', 'name']
    
    fieldsets = (
        ('Información', {
            'fields': ('code', 'name', 'symbol', 'decimal_places')
        }),
        ('Configuración', {
            'fields': ('is_base', 'is_active'),
            'description': 'Solo una moneda puede ser la base del sistema'
        }),
    )
    
    @admin.display(description='Moneda Base')
    def is_base_badge(self, obj):
        if obj.is_base:
            return "✅ Base"
        return "-"

@admin.register(ExchangeRate)
class ExchangeRateAdmin( UnfoldModelAdmin, SimpleHistoryAdmin):
    list_display = ['from_currency', 'to_currency', 'rate_display', 'date', 'source', 'user']
    list_filter = ['from_currency', 'to_currency', 'date']
    search_fields = ['source']
    
    fieldsets = (
        ('Tasa de Cambio', {
            'fields': ('from_currency', 'to_currency', 'rate')
        }),
        ('Información', {
            'fields': ('source', 'user')
        }),
    )
    
    @admin.display(description='Tasa')
    def rate_display(self, obj):
        return f"{obj.rate:.2f}"


@admin.register(PaymentMethod)
class PaymentMethodAdmin(UnfoldModelAdmin, SimpleHistoryAdmin):
    list_display = ['name', 'code', 'is_active_badge', 'requires_approval_badge', 'icon', 'default_currency']
    list_filter = ['is_active', 'requires_approval']
    search_fields = ['name', 'code']
    
    fieldsets = (
        ('Información', {
            'fields': ('name', 'code', 'description')
        }),
        ('Configuración', {
            'fields': ('is_active', 'requires_approval', 'icon', 'default_currency')
        }),
    )
    
    @admin.display(description='Activo')
    def is_active_badge(self, obj):
        if obj.is_active:
            return "✅ Activo"
        return "❌ Inactivo"
    
    @admin.display(description='Requiere Aprobación')
    def requires_approval_badge(self, obj):
        if obj.requires_approval:
            return "⚠️ Sí"
        return "No"