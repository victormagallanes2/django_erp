# rrhh/admin.py
from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from unfold.admin import ModelAdmin as UnfoldModelAdmin
from unfold.admin import StackedInline as UnfoldStackedInline
from unfold.admin import TabularInline as UnfoldTabularInline
from .models import Employee, Commission
from django.utils.html import format_html


class CommissionInline(UnfoldTabularInline):
    """Inline de comisiones dentro del empleado"""
    model = Commission
    extra = 0
    can_delete = False
    fields = ['sale_invoice', 'base_amount', 'rate', 'amount', 'status', 'created_at']
    readonly_fields = ['sale_invoice', 'base_amount', 'rate', 'amount', 'status', 'created_at']
    verbose_name_plural = _("Comisiones")


@admin.register(Commission)
class CommissionAdmin(UnfoldModelAdmin):
    """Admin de comisiones"""
    
    list_display = [
        'employee',
        'invoice_number',
        'base_amount_display',
        'rate',
        'amount_display',
        'status_badge',
        'created_at',
    ]
    
    list_filter = ['status', 'employee', 'created_at']
    search_fields = [
        'employee__user__username',
        'employee__user__first_name',
        'employee__user__last_name',
        'employee__employee_code',
        'sale_invoice__number',
    ]
    date_hierarchy = 'created_at'
    
    readonly_fields = [
        'employee', 'sale_invoice', 'base_amount', 'rate', 'amount', 'created_at'
    ]
    
    fieldsets = (
        (_('Comisión'), {
            'fields': ('employee', 'sale_invoice', 'base_amount', 'rate', 'amount')
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
            '<span style="background: {}; color: white; padding: 2px 10px; border-radius: 12px; font-size: 12px;">{}</span>',
            color, label
        )
    
    @admin.action(description=_('Marcar como pagadas'))
    def mark_as_paid(self, request, queryset):
        updated = queryset.filter(status='PENDING').update(
            status='PAID',
            paid_at=timezone.now()
        )
        self.message_user(request, f'{updated} comisiones marcadas como pagadas.')
    
    # ✅ No permitir crear/eliminar manualmente
    def has_add_permission(self, request):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False




class EmployeeInline(UnfoldStackedInline):
    model = Employee
    can_delete = False
    verbose_name = _("Datos de Empleado")
    verbose_name_plural = _("Datos de Empleado")
    # ✅ Solo campos editables de RRHH, sin is_active_employee
    fields = ('position', 'hire_date')
    extra = 0


@admin.register(Employee)
class EmployeeAdmin(UnfoldModelAdmin):
    """Admin de empleados - SOLO LECTURA Y EDICIÓN, NO CREACIÓN"""
    
    list_display = [
        'user_display',
        'employee_code',
        'position',
        'hire_date',
        'is_active_display',
        'commission_rate',  # ✅ Propiedad calculada
    ]
    
    list_filter = [
        'hire_date',
        'position',
        'user__is_employee',  # ✅ Filtrar por el campo del User
    ]
    
    search_fields = [
        'user__username',
        'user__first_name',
        'user__last_name',
        'user__email',
        'employee_code'
    ]
    
    fieldsets = (
        (_('Información del Empleado'), {
            'fields': ('position', 'hire_date', 'commission_rate')
        }),
        (_('Información del Usuario (Solo lectura)'), {
            'fields': ('user_display_readonly', 'employee_code'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ['user_display_readonly', 'employee_code']
    inlines = [CommissionInline]
    
    def has_add_permission(self, request):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False
    
    def user_display(self, obj):
        return obj.user.get_full_name() or obj.user.username
    user_display.short_description = _("Usuario")
    user_display.admin_order_field = 'user__username'
    
    def user_display_readonly(self, obj):
        return f"{obj.user.get_full_name()} ({obj.user.username}) - {obj.user.email}"
    user_display_readonly.short_description = _("Usuario")
    
    # ✅ Mostrar el estado usando la propiedad del modelo
    def is_active_display(self, obj):
        return obj.is_active
    is_active_display.short_description = _("Activo")
    is_active_display.boolean = True


