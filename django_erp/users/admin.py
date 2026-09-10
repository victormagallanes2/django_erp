# users/admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _
from unfold.admin import ModelAdmin as UnfoldModelAdmin
from unfold.admin import StackedInline as UnfoldStackedInline
from unfold.forms import AdminPasswordChangeForm, UserChangeForm, UserCreationForm  # ✅ IMPORTANTE
from django_erp.rrhh.models import Employee
from django_erp.rrhh.admin import EmployeeInline
from .models import User



@admin.register(User)
class UserAdmin(UnfoldModelAdmin, BaseUserAdmin):
    form = UserChangeForm
    add_form = UserCreationForm
    change_password_form = AdminPasswordChangeForm
    
    list_display = ['username', 'email', 'first_name', 'last_name', 'is_employee', 'is_staff', 'is_active']
    list_filter = ['is_staff', 'is_active', 'is_employee', 'groups']
    search_fields = ['username', 'email', 'first_name', 'last_name']
    ordering = ['username']
    
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        (_('Información Personal'), {'fields': ('first_name', 'last_name', 'email')}),
        # ✅ is_employee aquí, único lugar donde se controla
        (_('Empleado'), {'fields': ('is_employee',)}),
        (_('Permisos'), {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
        }),
        (_('Fechas importantes'), {'fields': ('last_login', 'date_joined')}),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email', 'first_name', 'last_name', 'is_employee', 'password1', 'password2'),
        }),
    )
    
    readonly_fields = ['date_joined']
    inlines = [EmployeeInline]
    
    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        # ✅ Crear Employee automáticamente si se marca is_employee
        if form.instance.is_employee and not hasattr(form.instance, 'employee'):
            Employee.objects.create(user=form.instance)