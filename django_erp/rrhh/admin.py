# rrhh/admin.py
from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from unfold.admin import ModelAdmin as UnfoldModelAdmin
from unfold.admin import StackedInline as UnfoldStackedInline
from .models import Employee



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
        'is_active_display',  # ✅ Propiedad calculada
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
            'fields': ('position', 'hire_date')
        }),
        (_('Información del Usuario (Solo lectura)'), {
            'fields': ('user_display_readonly', 'employee_code'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ['user_display_readonly', 'employee_code']
    
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