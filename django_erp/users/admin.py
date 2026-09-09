# users/admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import UserChangeForm, UserCreationForm
from django.utils.translation import gettext_lazy as _
from unfold.admin import ModelAdmin as UnfoldModelAdmin
from .models import User
from django_erp.rrhh.models import Employee



class EmployeeInline(admin.StackedInline):
    """Inline para crear/editar empleado desde el usuario"""
    model = Employee
    can_delete = False
    verbose_name = _("Datos de Empleado")
    verbose_name_plural = _("Datos de Empleado")
    fields = ('employee_code', 'position', 'hire_date', 'is_active_employee')
    readonly_fields = ['employee_code']  # Auto-generado
    extra = 0  # No mostrar inline vacío


class UserCreationFormCustom(UserCreationForm):
    """Formulario personalizado para crear usuarios"""
    
    class Meta:
        model = User
        fields = ('username', 'email', 'first_name', 'last_name')


class UserChangeFormCustom(UserChangeForm):
    """Formulario personalizado para editar usuarios"""
    
    class Meta:
        model = User
        fields = '__all__'


@admin.register(User)
class UserAdmin(UnfoldModelAdmin, BaseUserAdmin):
    """Admin de usuarios personalizado con hasheo de contraseñas"""
    
    # ✅ Formularios correctos para hashear contraseñas
    form = UserChangeFormCustom
    add_form = UserCreationFormCustom
    
    # ✅ Campos a mostrar en el listado
    list_display = ['username', 'email', 'first_name', 'last_name', 'is_employee', 'is_staff', 'is_active']
    list_filter = ['is_staff', 'is_active', 'groups', 'is_employee']
    search_fields = ['username', 'email', 'first_name', 'last_name']
    ordering = ['username']
    inlines = [EmployeeInline]
    
    # ✅ Campos en el formulario
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        (_('Información Personal'), {'fields': ('first_name', 'last_name', 'email')}),
        (_('Permisos'), {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'is_employee', 'groups', 'user_permissions'),
        }),
        (_('Fechas importantes'), {'fields': ('last_login', 'date_joined')}),
    )
    
    # ✅ Campos para el formulario de creación
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email', 'first_name', 'last_name', 'is_employee', 'password1', 'password2'),
        }),
    )
    
    # ✅ Los campos de contraseña se manejan automáticamente con los formularios correctos
    readonly_fields = ['date_joined']


