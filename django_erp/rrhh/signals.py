# rrhh/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings
from .models import Employee


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def handle_employee_on_user_change(sender, instance, **kwargs):
    """Crear Employee automáticamente si el usuario se marca como empleado"""
    if instance.is_employee and not hasattr(instance, 'employee'):
        Employee.objects.create(user=instance)