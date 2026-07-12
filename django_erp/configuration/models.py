# configuration/models.py
from django.db import models
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from simple_history.models import HistoricalRecords
from decimal import Decimal

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


class Currency(models.Model):
    """Moneda configurable"""
    
    code = models.CharField(max_length=10, unique=True, verbose_name="Código")
    name = models.CharField(max_length=50, verbose_name="Nombre")
    symbol = models.CharField(max_length=5, verbose_name="Símbolo")
    decimal_places = models.IntegerField(default=2, verbose_name="Decimales")
    
    is_base = models.BooleanField(
        default=False, 
        verbose_name="¿Es moneda base?",
        help_text="Solo una moneda puede ser la base. Ej: USD, EUR, etc."
    )
    is_active = models.BooleanField(default=True, verbose_name="Activo")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    history = HistoricalRecords()
    
    class Meta:
        verbose_name = "Moneda"
        verbose_name_plural = "Monedas"
        ordering = ['code']
    
    def __str__(self):
        return f"{self.code} - {self.symbol}"
    
    def save(self, *args, **kwargs):
        if self.is_base:
            Currency.objects.filter(is_base=True).exclude(pk=self.pk).update(is_base=False)
        super().save(*args, **kwargs)
    
    @classmethod
    def get_base(cls):
        return cls.objects.filter(is_base=True).first()


class ExchangeRate(models.Model):
    """Tasa de cambio entre monedas"""
    
    from_currency = models.ForeignKey(
        Currency,
        on_delete=models.CASCADE,
        related_name='rates_from',
        verbose_name="De"
    )
    to_currency = models.ForeignKey(
        Currency,
        on_delete=models.CASCADE,
        related_name='rates_to',
        verbose_name="A"
    )
    rate = models.DecimalField(
        max_digits=20,
        decimal_places=6,
        verbose_name="Tasa de cambio"
    )
    date = models.DateField(auto_now_add=True, verbose_name="Fecha")
    source = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Fuente"
    )
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name="Usuario"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    history = HistoricalRecords()
    
    class Meta:
        verbose_name = "Tasa de Cambio"
        verbose_name_plural = "Tasas de Cambio"
        ordering = ['-date']
        unique_together = [['from_currency', 'to_currency', 'date']]
    
    def __str__(self):
        return f"1 {self.from_currency.code} = {self.rate} {self.to_currency.code}"
    
    @classmethod
    def get_rate(cls, from_code, to_code, date=None):
        from datetime import date as date_type
        if date is None:
            date = date_type.today()
        
        from_currency = Currency.objects.get(code=from_code)
        to_currency = Currency.objects.get(code=to_code)
        
        if from_currency == to_currency:
            return Decimal('1')
        
        rate = cls.objects.filter(
            from_currency=from_currency,
            to_currency=to_currency,
            date=date
        ).first()
        
        if not rate:
            rate = cls.objects.filter(
                from_currency=from_currency,
                to_currency=to_currency
            ).order_by('-date').first()
        
        return rate.rate if rate else Decimal('1')
    
    @classmethod
    def get_today_rate(cls, from_code, to_code):
        from datetime import date as date_type
        today = date_type.today()
        return cls.get_rate(from_code, to_code, today)