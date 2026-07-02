# configuration/models.py
from django.db import models
from django.core.exceptions import ValidationError


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