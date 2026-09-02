# accounting/models.py
from django.db import models
from django.core.exceptions import ValidationError
from simple_history.models import HistoricalRecords
from decimal import Decimal
import datetime
from django.contrib.auth import get_user_model
from django_erp.configuration.models import Company, Currency

User = get_user_model()


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


class ExchangeRate(models.Model):
    """✅ TASA DE CAMBIO POR COMPAÑÍA - Con historial completo para contabilidad"""
    
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
    date = models.DateField(
        auto_now_add=True, 
        verbose_name="Fecha",
        help_text="Fecha en que se registró esta tasa"
    )
    effective_date = models.DateField(
        default=datetime.date.today,  # ✅ Mejor que auto_now_add
        verbose_name="Fecha de vigencia",
        help_text="Fecha desde la cual aplica esta tasa"
    )
    source = models.CharField(
        max_length=100,
        default='Manual',
        editable=False,
        verbose_name="Fuente"
    )
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        editable=False,
        verbose_name="Usuario que registró"
    )
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        editable=False,
        verbose_name="Compañía/Sucursal",
        related_name='exchangerate'
    )
    created_at = models.DateTimeField(auto_now_add=True, editable=False)
    updated_at = models.DateTimeField(auto_now=True, editable=False)
    history = HistoricalRecords()
    
    class Meta:
        verbose_name = "Tasa de Cambio"
        verbose_name_plural = "Tasas de Cambio"
        ordering = ['-date', '-created_at']
        unique_together = [
            ['company', 'from_currency', 'to_currency', 'date', 'created_at']
        ]
        indexes = [
            models.Index(fields=['company', 'date']),
            models.Index(fields=['from_currency', 'to_currency']),
            models.Index(fields=['company', 'from_currency', 'to_currency', '-date']),
        ]

    def __str__(self):
        return f"1 {self.from_currency.code} = {self.rate} {self.to_currency.code} ({self.company.code})"
    
    def save(self, *args, **kwargs):
        # ✅ Si no tiene fuente, asignar 'Manual'
        if not self.source:
            self.source = 'Manual'
        
        super().save(*args, **kwargs)
    
    @classmethod
    def get_rate(cls, from_code, to_code, company=None, date=None):
        """Obtener la tasa de cambio VIGENTE para una fecha específica"""
        from datetime import date as date_type
        from decimal import Decimal
        
        if date is None:
            date = date_type.today()
        
        if company is None:
            from .models import Company
            company = Company.get_active()
        
        if not company:
            return Decimal('1')
        
        try:
            from_currency = Currency.objects.get(code=from_code)
            to_currency = Currency.objects.get(code=to_code)
        except Currency.DoesNotExist:
            return Decimal('1')
        
        if from_currency == to_currency:
            return Decimal('1')
        
        rate = cls.objects.filter(
            company=company,
            from_currency=from_currency,
            to_currency=to_currency,
            effective_date__lte=date
        ).order_by(
            '-effective_date',
            '-created_at'
        ).first()
        
        if not rate:
            rate = cls.objects.filter(
                company=company,
                from_currency=from_currency,
                to_currency=to_currency
            ).order_by('-effective_date', '-created_at').first()
        
        return rate.rate if rate else Decimal('1')
    
    @classmethod
    def get_today_rate(cls, from_code, to_code, company=None):
        """Obtener la tasa de cambio VIGENTE para hoy"""
        from datetime import date as date_type
        today = date_type.today()
        return cls.get_rate(from_code, to_code, company, today)
    
    @classmethod
    def get_historical_rates(cls, from_code, to_code, company=None, days=30):
        """Obtener el historial de tasas de cambio para los últimos N días"""
        from datetime import date as date_type, timedelta
        
        if company is None:
            from .models import Company
            company = Company.get_active()
        
        if not company:
            return []
        
        try:
            from_currency = Currency.objects.get(code=from_code)
            to_currency = Currency.objects.get(code=to_code)
        except Currency.DoesNotExist:
            return []
        
        if from_currency == to_currency:
            return []
        
        start_date = date_type.today() - timedelta(days=days)
        
        rates = cls.objects.filter(
            company=company,
            from_currency=from_currency,
            to_currency=to_currency,
            effective_date__gte=start_date
        ).order_by('effective_date', 'created_at')
        
        return rates