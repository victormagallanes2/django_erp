# django_erp/accounting/admin.py
from django.contrib import admin
from unfold.admin import ModelAdmin as UnfoldModelAdmin
from unfold.admin import TabularInline as UnfoldTabularInline
from simple_history.admin import SimpleHistoryAdmin
from django.contrib import messages
from .models import Tax, TaxRate, ExchangeRate
from django_erp.configuration.mixins import CompanyFilterMixin
from django_erp.configuration.models import Company



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


@admin.register(ExchangeRate)
class ExchangeRateAdmin(CompanyFilterMixin, UnfoldModelAdmin, SimpleHistoryAdmin):
    """
    Admin de tasas de cambio con filtro por compañía activa.
    """
    
    fields = ('from_currency', 'to_currency', 'rate')
    
    list_display = ['from_currency', 'to_currency', 'rate_display', 'date', 'company', 'user']
    list_filter = ['from_currency', 'to_currency', 'date']
    search_fields = ['from_currency__code', 'to_currency__code', 'company__name', 'company__code']
    
    readonly_fields = ['date', 'effective_date', 'source', 'user', 'company', 'created_at', 'updated_at']
    exclude = ['note']
    
    @admin.display(description='Tasa')
    def rate_display(self, obj):
        return f"{obj.rate:.4f}"
    
    def save_model(self, request, obj, form, change):
        from datetime import date
        
        # ✅ Compañía activa
        company = getattr(request, 'current_company', None)
        if not company:
            company = Company.get_active()
        
        if company:
            obj.company = company
        
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
        """Filtrar por compañía activa usando CompanyFilterMixin"""
        queryset = super().get_queryset(request)
        company = self._get_active_company(request)
        
        if company:
            return queryset.filter(company=company)
        
        return queryset.none()
    
    def has_change_permission(self, request, obj=None):
        if obj:
            return False
        return True
    
    def get_changeform_initial_data(self, request):
        initial = super().get_changeform_initial_data(request)
        try:
            initial['from_currency'] = Currency.objects.get(code='USD').pk
            initial['to_currency'] = Currency.objects.get(code='BS').pk
        except Currency.DoesNotExist:
            pass
        return initial