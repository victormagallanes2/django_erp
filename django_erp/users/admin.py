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
from django.utils.html import format_html
from django.utils.safestring import mark_safe



@admin.register(User)
class UserAdmin(UnfoldModelAdmin, BaseUserAdmin):
    form = UserChangeForm
    add_form = UserCreationForm
    change_password_form = AdminPasswordChangeForm

    list_display = [
        'username', 'email', 'first_name', 'last_name',
        'is_employee', 'is_staff', 'is_active', 'companies_display',
    ]
    list_filter = ['is_staff', 'is_active', 'is_employee', 'groups', 'companies']
    search_fields = ['username', 'email', 'first_name', 'last_name']
    ordering = ['username']

    # ✅ Filtro horizontal para M2M (más cómodo que el select múltiple por defecto)
    filter_horizontal = ['companies', 'groups', 'user_permissions']

    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        (_('Información Personal'), {'fields': ('first_name', 'last_name', 'email')}),
        # ✅ is_employee aquí, único lugar donde se controla
        (_('Empleado'), {'fields': ('is_employee',)}),
        # ✅ NUEVO: bloque de compañías asignadas
        (_('Compañías asignadas'), {
            'fields': ('companies',),
            'description': (
                'Selecciona las compañías a las que este usuario tiene acceso. '
                'Si es empleado, su compañía activa será la primera de esta lista.'
            ),
        }),
        (_('Permisos'), {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
        }),
        (_('Fechas importantes'), {'fields': ('last_login', 'date_joined')}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': (
                'username', 'email', 'first_name', 'last_name',
                'is_employee', 'companies',  # ✅ NUEVO
                'password1', 'password2',
            ),
        }),
    )

    readonly_fields = ['date_joined']
    inlines = [EmployeeInline]

    @admin.display(description=_("Compañías"))
    def companies_display(self, obj):
        """Mostrar las compañías asignadas en la lista"""
        companies = obj.companies.filter(is_active=True)
        if not companies.exists():
            return mark_safe(
                '<span style="color: #dc3545; font-weight: bold;">⚠️ Sin compañías</span>'
            )
        return ", ".join([c.code for c in companies])

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        # ✅ Crear Employee automáticamente si se marca is_employee
        if form.instance.is_employee and not hasattr(form.instance, 'employee'):
            Employee.objects.create(user=form.instance)