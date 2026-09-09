# rrhh/models.py
from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _


class Employee(models.Model):
    """Modelo básico de empleado relacionado con User"""
    
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='employee',
        verbose_name=_("Usuario")
    )
    
    employee_code = models.CharField(
        max_length=20,
        unique=True,
        verbose_name=_("Código de empleado")
    )
    
    hire_date = models.DateField(
        verbose_name=_("Fecha de contratación"),
        null=True,
        blank=True
    )
    
    position = models.CharField(
        max_length=100,
        verbose_name=_("Cargo"),
        blank=True
    )
    
    is_active_employee = models.BooleanField(
        default=True,
        verbose_name=_("Empleado activo")
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = _("Empleado")
        verbose_name_plural = _("Empleados")
        ordering = ['user__first_name', 'user__last_name']
    
    def __str__(self):
        return f"{self.user.get_full_name()} ({self.employee_code})"
    
    def save(self, *args, **kwargs):
        # Auto-generar código de empleado si no se proporciona
        if not self.employee_code:
            # Ejemplo: EMP-0001, EMP-0002, etc.
            last_employee = Employee.objects.order_by('-id').first()
            if last_employee:
                last_code = int(last_employee.employee_code.split('-')[1])
                self.employee_code = f"EMP-{str(last_code + 1).zfill(4)}"
            else:
                self.employee_code = "EMP-0001"
        super().save(*args, **kwargs)