# configuration/admin.py
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse, path
from django.contrib import messages
from django.shortcuts import redirect
from django.http import FileResponse
from simple_history.admin import SimpleHistoryAdmin
from unfold.admin import ModelAdmin as UnfoldModelAdmin
from .services import BackupService
from .models import Currency, ExchangeRate, CompanyBankAccount, Company, Backup, PaymentMethod
import os
from django_erp.configuration.mixins import CompanyFilterMixin
from django import forms
from unfold.widgets import UnfoldAdminSelectWidget


@admin.register(Company)
class CompanyAdmin(UnfoldModelAdmin):
    """Admin de compañías - Ahora gestiona múltiples compañías"""
    
    list_display = ['code', 'name', 'rif', 'is_main', 'parent', 'is_active']
    list_filter = ['is_main', 'is_active']
    search_fields = ['code', 'name', 'rif']
    change_list_template = "admin/configuration/company_changelist.html"
    
    fieldsets = (
        ('Identificación', {
            'fields': ('code', 'name', 'trade_name', 'rif', 'parent')
        }),
        ('Contacto', {
            'fields': ('address', 'phone', 'email', 'website', 'logo')
        }),
        ('Configuración', {
            'fields': ('tax_rate', 'default_currency', 'invoice_prefix', 'control_number_required')
        }),
        ('Estado', {
            'fields': ('is_main', 'is_active')
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

    def save_model(self, request, obj, form, change):
        """Al guardar, verificar que la compañía principal tenga su propio código"""
        if obj.is_main and not obj.code:
            obj.code = 'MAIN'
        super().save_model(request, obj, form, change)
    
    def get_queryset(self, request):
        """Los superusuarios ven todas, los demás solo las que tienen asignadas"""
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(users=request.user)


@admin.register(Backup)
class BackupAdmin(CompanyFilterMixin, UnfoldModelAdmin, SimpleHistoryAdmin):
    """Admin de respaldos - Solo crear"""
    
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
    
    def get_actions(self, request):
        return {}


@admin.register(Currency)
class CurrencyAdmin(UnfoldModelAdmin, SimpleHistoryAdmin):
    """✅ Admin de monedas GLOBALES - No usa CompanyFilterMixin"""
    
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
class ExchangeRateAdmin(CompanyFilterMixin, UnfoldModelAdmin, SimpleHistoryAdmin):
    """Admin de tasas de cambio - SIMPLE"""
    
    # ✅ Los 3 campos que el usuario ve
    fields = ('from_currency', 'to_currency', 'rate')
    
    # ✅ Listado
    list_display = ['from_currency', 'to_currency', 'rate_display', 'date', 'company', 'user']
    list_filter = ['from_currency', 'to_currency', 'date', 'company']
    search_fields = ['from_currency__code', 'to_currency__code']
    
    # ✅ Campos ocultos que se autollenan
    readonly_fields = ['date', 'effective_date', 'source', 'user', 'company', 'created_at', 'updated_at']
    exclude = ['note']
    
    @admin.display(description='Tasa')
    def rate_display(self, obj):
        return f"{obj.rate:.4f}"
    
    def save_model(self, request, obj, form, change):
        from datetime import date
        
        # ✅ Autollenar todo
        obj.company = Company.get_active()
        obj.user = request.user
        obj.source = 'Manual'
        obj.effective_date = date.today()
        obj.date = date.today()
        
        super().save_model(request, obj, form, change)
        
        self.message_user(
            request,
            f'✅ Tasa registrada: 1 {obj.from_currency.code} = {obj.rate} {obj.to_currency.code}',
            messages.SUCCESS
        )
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        company = Company.get_active()
        if company:
            qs = qs.filter(company=company)
        return qs
    
    def has_change_permission(self, request, obj=None):
        if obj:
            return False
        return True
    
    # ✅ Valores por defecto - ESTO ES LO QUE FUNCIONA
    def get_changeform_initial_data(self, request):
        initial = super().get_changeform_initial_data(request)
        try:
            initial['from_currency'] = Currency.objects.get(code='USD').pk
            initial['to_currency'] = Currency.objects.get(code='BS').pk
        except Currency.DoesNotExist:
            pass
        return initial


@admin.register(PaymentMethod)
class PaymentMethodAdmin(CompanyFilterMixin, UnfoldModelAdmin, SimpleHistoryAdmin):
    """✅ Admin de métodos de pago POR COMPAÑÍA"""
    
    list_display = ['name', 'code', 'is_active_badge', 'requires_approval_badge', 'icon', 'default_currency', 'company']
    list_filter = ['is_active', 'requires_approval', 'company']
    search_fields = ['name', 'code']
    autocomplete_fields = ['default_currency']
    
    fieldsets = (
        ('Información', {
            'fields': ('name', 'code', 'description')
        }),
        ('Configuración', {
            'fields': ('is_active', 'requires_approval', 'icon', 'default_currency', 'company')
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


@admin.register(CompanyBankAccount)
class CompanyBankAccountAdmin(CompanyFilterMixin, UnfoldModelAdmin, SimpleHistoryAdmin):
    """Admin de cuentas bancarias POR COMPAÑÍA"""
    
    list_display = [
        'bank_name', 
        'account_number', 
        'account_holder', 
        'currency', 
        'is_default_badge', 
        'is_active',
        'company'
    ]
    list_filter = ['currency', 'is_active', 'is_default', 'company']
    search_fields = ['bank_name', 'account_number', 'account_holder']
    autocomplete_fields = ['currency']
    
    fieldsets = (
        ('Datos de la Cuenta', {
            'fields': ('bank_name', 'account_type', 'account_number', 'account_holder')
        }),
        ('Moneda', {
            'fields': ('currency',)
        }),
        ('Configuración', {
            'fields': ('is_default', 'is_active', 'company')
        }),
    )
    
    @admin.display(description='Por Defecto')
    def is_default_badge(self, obj):
        if obj.is_default:
            return "⭐ Sí"
        return "-"
    
    def save_model(self, request, obj, form, change):
        if obj.is_default:
            CompanyBankAccount.objects.filter(is_default=True).exclude(pk=obj.pk).update(is_default=False)
        super().save_model(request, obj, form, change)