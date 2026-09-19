# rrhh/admin.py
from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from django.utils.html import format_html
from django.utils import timezone
from unfold.admin import ModelAdmin as UnfoldModelAdmin
from unfold.admin import StackedInline as UnfoldStackedInline
from unfold.admin import TabularInline as UnfoldTabularInline
from .models import Employee, Commission
from django_erp.configuration.mixins import CompanyFilterMixin


# ============================================================
# INLINE DE COMISIONES (dentro del empleado)
# ============================================================
class CommissionInline(UnfoldTabularInline):
    """Inline de comisiones dentro del empleado"""
    model = Commission
    extra = 0
    can_delete = False
    fields = ['sale_invoice', 'base_amount', 'rate', 'amount', 'status', 'created_at']
    readonly_fields = ['sale_invoice', 'base_amount', 'rate', 'amount', 'status', 'created_at']
    verbose_name_plural = _("Comisiones")


# ============================================================
# ADMIN DE COMISIONES
# ============================================================
@admin.register(Commission)
class CommissionAdmin(CompanyFilterMixin, UnfoldModelAdmin):
    """Admin de comisiones - filtrado por compañía activa"""

    list_display = [
        'employee',
        'invoice_number',
        'company_display',
        'base_amount_display',
        'rate',
        'amount_display',
        'status_badge',
        'created_at',
    ]

    list_filter = ['status', 'company', 'employee', 'created_at']
    search_fields = [
        'employee__user__username',
        'employee__user__first_name',
        'employee__user__last_name',
        'employee__employee_code',
        'sale_invoice__number',
    ]
    date_hierarchy = 'created_at'

    readonly_fields = [
        'employee', 'sale_invoice', 'company',
        'base_amount', 'rate', 'amount', 'created_at'
    ]

    fieldsets = (
        (_('Comisión'), {
            'fields': ('employee', 'sale_invoice', 'company', 'base_amount', 'rate', 'amount')
        }),
        (_('Estado'), {
            'fields': ('status', 'paid_at')
        }),
        (_('Auditoría'), {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )

    actions = ['mark_as_paid']

    # ============================================================
    # ✅ FILTRAR POR COMPAÑÍA ACTIVA (ahora con campo directo)
    # ============================================================
    def get_queryset(self, request):
        """
        Filtrar las comisiones por la compañía activa.
        Ahora Commission tiene FK directa a Company → filtro simple.
        """
        qs = super().get_queryset(request)
        company = getattr(request, 'current_company', None)
        if company:
            qs = qs.filter(company=company)
        return qs

    # ============================================================
    # COLUMNA DE COMPAÑÍA
    # ============================================================
    @admin.display(description=_('Compañía'), ordering='company__name')
    def company_display(self, obj):
        if obj.company:
            return obj.company.code
        return '—'

    # ============================================================
    # DISPLAYS
    # ============================================================
    @admin.display(description=_('Factura'), ordering='sale_invoice__number')
    def invoice_number(self, obj):
        return obj.sale_invoice.number if obj.sale_invoice else '—'

    @admin.display(description=_('Base (sin IVA)'))
    def base_amount_display(self, obj):
        return f"$ {obj.base_amount:.2f}"

    @admin.display(description=_('Comisión'))
    def amount_display(self, obj):
        return f"$ {obj.amount:.2f}"

    @admin.display(description=_('Estado'), ordering='status')
    def status_badge(self, obj):
        colors = {
            'PENDING': ('#ffc107', '⏳ Pendiente'),
            'PAID': ('#28a745', '✅ Pagada'),
            'CANCELLED': ('#dc3545', '❌ Cancelada'),
        }
        color, label = colors.get(obj.status, ('#6c757d', obj.status))
        return format_html(
            '<span style="background: {}; color: white; padding: 2px 10px; '
            'border-radius: 12px; font-size: 12px;">{}</span>',
            color, label
        )

    @admin.action(description=_('Marcar como pagadas'))
    def mark_as_paid(self, request, queryset):
        # ✅ El queryset ya viene filtrado por compañía
        updated = queryset.filter(status='PENDING').update(
            status='PAID',
            paid_at=timezone.now()
        )
        self.message_user(request, f'{updated} comisiones marcadas como pagadas.')

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


# ============================================================
# INLINE DE EMPLEADO (dentro del User)
# ============================================================
class EmployeeInline(UnfoldStackedInline):
    model = Employee
    can_delete = False
    verbose_name = _("Datos de Empleado")
    verbose_name_plural = _("Datos de Empleado")
    fields = ('position', 'hire_date')
    extra = 0


# ============================================================
# ADMIN DE EMPLEADOS
# ============================================================
@admin.register(Employee)
class EmployeeAdmin(UnfoldModelAdmin):
    """Admin de empleados - SOLO LECTURA Y EDICIÓN, NO CREACIÓN"""

    list_display = [
        'user_display',
        'employee_code',
        'companies_display',
        'position',
        'hire_date',
        'is_active_display',
        'commission_rate',
        'pin',
    ]

    list_filter = ['hire_date', 'position', 'user__is_employee']

    search_fields = [
        'user__username',
        'user__first_name',
        'user__last_name',
        'user__email',
        'employee_code',
        'pin',
    ]

    fieldsets = (
        (_('Información del Empleado'), {
            'fields': ('position', 'hire_date')
        }),
        (_('Información del Usuario (Solo lectura)'), {
            'fields': ('user_display_readonly', 'employee_code', 'companies_display'),
            'classes': ('collapse',)
        }),
        (_('Acceso y Comisiones'), {
            'fields': ('pin', 'commission_rate'),
        }),
    )

    readonly_fields = ['user_display_readonly', 'employee_code', 'companies_display']
    inlines = [CommissionInline]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.display(description=_("Usuario"), ordering='user__username')
    def user_display(self, obj):
        return obj.user.get_full_name() or obj.user.username

    @admin.display(description=_("Usuario"))
    def user_display_readonly(self, obj):
        return f"{obj.user.get_full_name()} ({obj.user.username}) - {obj.user.email}"

    @admin.display(description=_("Compañías"))
    def companies_display(self, obj):
        companies = obj.user.companies.filter(is_active=True)
        if not companies.exists():
            return format_html(
                '<span style="color: #dc3545; font-weight: bold;">'
                '⚠️ Sin compañías'
                '</span>'
            )
        return ", ".join([c.code for c in companies])

    @admin.display(description=_("Activo"), boolean=True)
    def is_active_display(self, obj):
        return obj.is_active