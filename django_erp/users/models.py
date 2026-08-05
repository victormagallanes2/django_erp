# users/models.py
from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Modelo de usuario personalizado"""
    
    email = models.EmailField(unique=True, verbose_name="Correo electrónico")
    companies = models.ManyToManyField(
        'configuration.Company',
        related_name='users',
        blank=True,
        verbose_name="Compañías asignadas",
        help_text="Compañías a las que el usuario tiene acceso"
    )
    
    # ✅ NUEVO: Compañía activa (se usa el middleware para establecerla)
    # No guardamos este campo en la BD, se maneja por sesión
    
    class Meta:
        verbose_name = "Usuario"
        verbose_name_plural = "Usuarios"
    
    def __str__(self):
        return self.username
    
    def get_available_companies(self):
        """Obtener todas las compañías disponibles para el usuario"""
        if self.is_superuser:
            return Company.get_active_companies()
        return self.companies.filter(is_active=True)

