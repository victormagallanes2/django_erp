# accounting/models.py
from django.db import models
from django.core.exceptions import ValidationError
from simple_history.models import HistoricalRecords
from decimal import Decimal

from django_erp.configuration.models import Company

class Tax(models.Model):
    """
    Modelo para definir diferentes tipos de impuestos.
    Ejemplo: IVA, Impuesto a la Renta, Impuesto Municipal, etc.
    """
    TAX_TYPE_CHOICES = [
        ('SALES', 'Impuesto sobre Ventas'),
        ('PURCHASE', 'Impuesto sobre Compras'),
        ('WITHHOLDING', 'Retención'),
        ('OTHER', 'Otro'),
    ]

    name = models.CharField(max_length=100, verbose_name="Nombre")
    code = models.CharField(max_length=20, unique=True, verbose_name="Código", help_text="Ej: VAT, ISLR, MUNICIPAL")
    description = models.TextField(blank=True, verbose_name="Descripción")
    tax_type = models.CharField(max_length=20, choices=TAX_TYPE_CHOICES, default='SALES', verbose_name="Tipo de Impuesto")
    is_active = models.BooleanField(default=True, verbose_name="Activo")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    history = HistoricalRecords()

    class Meta:
        verbose_name = "Impuesto"
        verbose_name_plural = "Impuestos"
        ordering = ['code']
        permissions = [
            ("can_view_tax", "Puede ver impuestos"),
            ("can_edit_tax", "Puede editar impuestos"),
            ("can_delete_tax", "Puede eliminar impuestos"),
        ]

    def __str__(self):
        return f"{self.code} - {self.name}"


class TaxRate(models.Model):
    """
    Modelo para las tasas de un impuesto específico, aplicable a una compañía.
    Esto permite que diferentes compañías tengan diferentes tasas de IVA.
    """
    tax = models.ForeignKey(
        Tax,
        on_delete=models.PROTECT,
        related_name='rates',
        verbose_name="Impuesto"
    )
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name='tax_rates',
        verbose_name="Compañía"
    )
    rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        verbose_name="Tasa (%)",
        help_text="Ej: 16.00 para 16%"
    )
    effective_date = models.DateField(
        verbose_name="Fecha de Vigencia",
        help_text="Fecha desde la cual aplica esta tasa"
    )
    is_default = models.BooleanField(
        default=False,
        verbose_name="¿Tasa por defecto?",
        help_text="Marca la tasa que se aplica por defecto para esta compañía e impuesto."
    )
    note = models.TextField(blank=True, verbose_name="Nota")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    history = HistoricalRecords()

    class Meta:
        verbose_name = "Tasa de Impuesto"
        verbose_name_plural = "Tasas de Impuesto"
        ordering = ['-effective_date']
        unique_together = [['tax', 'company', 'effective_date']]
        indexes = [
            models.Index(fields=['company', 'tax', 'effective_date']),
        ]
        permissions = [
            ("can_view_taxrate", "Puede ver tasas de impuesto"),
            ("can_edit_taxrate", "Puede editar tasas de impuesto"),
            ("can_delete_taxrate", "Puede eliminar tasas de impuesto"),
        ]

    def __str__(self):
        return f"{self.tax.code} ({self.rate}%) - {self.company.code}"

    def clean(self):
        if self.rate < 0:
            raise ValidationError("La tasa no puede ser negativa.")

    def save(self, *args, **kwargs):
        self.full_clean()
        # Si se marca como por defecto, desmarcar las otras por defecto para la misma compañía e impuesto
        if self.is_default:
            TaxRate.objects.filter(
                tax=self.tax,
                company=self.company,
                is_default=True
            ).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)

    @classmethod
    def get_current_rate(cls, tax_code, company, date=None):
        """
        Obtiene la tasa de impuesto vigente para una compañía en una fecha específica.
        """
        from datetime import date as date_type
        if date is None:
            date = date_type.today()
        
        try:
            tax = Tax.objects.get(code=tax_code)
        except Tax.DoesNotExist:
            return Decimal('0.00')

        rate_obj = cls.objects.filter(
            tax=tax,
            company=company,
            effective_date__lte=date,
            tax__is_active=True
        ).order_by(
            '-is_default',  # Priorizar la tasa por defecto
            '-effective_date'
        ).first()
        
        return rate_obj.rate if rate_obj else Decimal('0.00')