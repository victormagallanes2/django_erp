# rrhh/admin.py
from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from unfold.admin import ModelAdmin as UnfoldModelAdmin
from .models import Employee


@admin.register(Employee)
class EmployeeAdmin(UnfoldModelAdmin):
    """Admin de empleados - SOLO LECTURA Y EDICIÓN, NO CREACIÓN"""
    
    list_display = [
        'user_display',
        'employee_code', 
        'position',
        'hire_date',
        'is_active_employee',
    ]
    
    list_filter = [
        'is_active_employee',
        'hire_date',
        'position'
    ]
    
    search_fields = [
        'user__username',
        'user__first_name',
        'user__last_name',
        'user__email',
        'employee_code'
    ]
    
    # ✅ SOLO campos editables por RRHH
    fieldsets = (
        (_('Información del Empleado'), {
            'fields': ('position', 'hire_date', 'is_active_employee')
        }),
        (_('Información del Usuario (Solo lectura)'), {
            'fields': ('user_display_readonly', 'employee_code'),
            'classes': ('collapse',)
        }),
    )
    
    # ✅ Hacer readonly los campos que no deben editarse
    readonly_fields = ['user_display_readonly', 'employee_code']
    
    # ✅ DESHABILITAR creación y eliminación
    def has_add_permission(self, request):
        return False  # ❌ No se pueden crear empleados desde aquí
    
    def has_delete_permission(self, request, obj=None):
        return False  # ❌ No se pueden eliminar empleados desde aquí
    
    # ✅ Métodos para mostrar información del usuario
    def user_display_readonly(self, obj):
        return f"{obj.user.get_full_name()} ({obj.user.username}) - {obj.user.email}"
    user_display_readonly.short_description = _("Usuario")
    
    def user_display(self, obj):
        return obj.user.get_full_name() or obj.user.username
    user_display.short_description = _("Usuario")
    user_display.admin_order_field = 'user__username'