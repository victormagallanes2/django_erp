# rrhh/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings
from .models import Employee


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def handle_employee_on_user_change(sender, instance, **kwargs):
    """Manejar creación/actualización de empleado cuando cambia el usuario"""
    
    # Si el usuario es empleado pero no tiene Employee, crearlo
    if instance.is_employee and not hasattr(instance, 'employee'):
        Employee.objects.create(
            user=instance,
            is_active_employee=True
        )
        return
    
    # Si tiene Employee, actualizar estado según is_employee
    if hasattr(instance, 'employee'):
        employee = instance.employee
        should_be_active = instance.is_employee
        
        if employee.is_active_employee != should_be_active:
            employee.is_active_employee = should_be_active
            employee.save(update_fields=['is_active_employee'])