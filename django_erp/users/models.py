# users/models.py
from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Modelo de usuario personalizado"""
    
    email = models.EmailField(unique=True, verbose_name="Correo electrónico")
    
    # ✅ Si quieres campos adicionales
    # phone = models.CharField(max_length=20, blank=True, verbose_name="Teléfono")
    # address = models.TextField(blank=True, verbose_name="Dirección")
    
    class Meta:
        verbose_name = "Usuario"
        verbose_name_plural = "Usuarios"
    
    def __str__(self):
        return self.username

