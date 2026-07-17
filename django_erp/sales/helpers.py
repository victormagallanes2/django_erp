# sales/helpers.py
from .models import CashRegister
from django.core.exceptions import ValidationError


def get_open_register(user):
    """Obtener la caja abierta de un usuario"""
    register = CashRegister.objects.filter(
        user=user,
        status='OPEN'
    ).first()
    
    if not register:
        raise ValidationError(
            f"No hay una caja abierta para {user.username}. "
            "Debe abrir una caja antes de realizar ventas."
        )
    
    return register


def has_open_register(user):
    """Verificar si el usuario tiene una caja abierta"""
    return CashRegister.objects.filter(
        user=user,
        status='OPEN'
    ).exists()