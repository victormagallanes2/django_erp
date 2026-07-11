# configuration/models.py
from django.db import models
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from simple_history.models import HistoricalRecords

import os


User = get_user_model()


class Company(models.Model):
    """Configuración de la empresa"""
    
    # Datos básicos
    name = models.CharField(max_length=200, verbose_name="Razón Social")
    rif = models.CharField(max_length=20, unique=True, verbose_name="RIF")
    trade_name = models.CharField(max_length=200, blank=True, verbose_name="Nombre Comercial")
    
    # Contacto
    address = models.TextField(verbose_name="Dirección Fiscal")
    phone = models.CharField(max_length=20, verbose_name="Teléfono")
    email = models.EmailField(verbose_name="Correo Electrónico")
    website = models.URLField(blank=True, verbose_name="Sitio Web")
    
    # Imagen
    logo = models.ImageField(
        upload_to='company/',
        blank=True,
        null=True,
        verbose_name="Logo"
    )
    
    # Configuración fiscal
    tax_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=16.00,
        verbose_name="Tasa de IVA (%)"
    )
    currency = models.CharField(
        max_length=10,
        default='Bs.D',
        verbose_name="Moneda"
    )
    
    # Configuración de facturación
    invoice_prefix = models.CharField(
        max_length=10,
        default='FAC',
        verbose_name="Prefijo de Factura"
    )
    control_number_required = models.BooleanField(
        default=False,
        verbose_name="¿Requiere Número de Control SENIAT?",
        help_text="Activar si la empresa usa imprenta digital autorizada"
    )
    
    # Activo
    is_active = models.BooleanField(default=True, verbose_name="Activo")
    
    # Auditoría
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Creado")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Actualizado")

    class Meta:
        verbose_name = "Configuración de la Empresa"
        verbose_name_plural = "Configuración de la Empresa"

    def __str__(self):
        return self.name

    def clean(self):
        """Validar que solo haya una empresa activa"""
        if self.is_active:
            existing = Company.objects.filter(is_active=True).exclude(pk=self.pk)
            if existing.exists():
                raise ValidationError("Ya existe una empresa activa. Desactiva la otra primero.")

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    @classmethod
    def get_active(cls):
        """Obtener la empresa activa"""
        return cls.objects.filter(is_active=True).first()


class Backup(models.Model):
    """Modelo para gestionar respaldos de la base de datos"""
    
    STATUS_CHOICES = [
        ('PENDING', 'Pendiente'),
        ('PROCESSING', 'Procesando'),
        ('COMPLETED', 'Completado'),
        ('FAILED', 'Fallido'),
    ]
    
    name = models.CharField(max_length=200, verbose_name="Nombre")
    file_path = models.CharField(max_length=500, verbose_name="Ruta del archivo")
    file_size = models.IntegerField(default=0, verbose_name="Tamaño (bytes)")
    
    database_type = models.CharField(max_length=50, default='sqlite', verbose_name="Tipo")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING', verbose_name="Estado")
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Creado")
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name="Completado")
    
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name="Usuario")
    note = models.TextField(blank=True, verbose_name="Notas")
    
    history = HistoricalRecords()
    
    class Meta:
        verbose_name = "Respaldo"
        verbose_name_plural = "Respaldos"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} - {self.created_at.strftime('%Y-%m-%d %H:%M')}"
    
    @property
    def file_size_display(self):
        if self.file_size < 1024:
            return f"{self.file_size} B"
        elif self.file_size < 1024 * 1024:
            return f"{self.file_size / 1024:.2f} KB"
        elif self.file_size < 1024 * 1024 * 1024:
            return f"{self.file_size / (1024 * 1024):.2f} MB"
        else:
            return f"{self.file_size / (1024 * 1024 * 1024):.2f} GB"