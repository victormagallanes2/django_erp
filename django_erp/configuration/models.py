# configuration/models.py
from django.db import models
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from simple_history.models import HistoricalRecords
from decimal import Decimal
import os
import datetime


User = get_user_model()


class Company(models.Model):
    """Configuración de la empresa"""
    
    # Datos básicos
    code = models.CharField(
        max_length=10, 
        unique=True, 
        verbose_name="Código",
        help_text="Código único para identificar la compañía/sucursal (ej: MATRIZ, SUC01, SUC02)"
    )
    parent = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Compañía Padre",
        help_text="Si es una sucursal, selecciona la compañía matriz"
    )
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

    # ✅ Moneda por defecto para esta compañía (Global)
    default_currency = models.ForeignKey(
        'configuration.Currency',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        verbose_name="Moneda por defecto",
        related_name='default_for_companies'
    )

    # ✅ ¿Es la compañía principal?
    is_main = models.BooleanField(
        default=False,
        verbose_name="¿Es compañía principal?",
        help_text="Solo una compañía puede ser la principal (matriz)"
    )
    # Activo
    is_active = models.BooleanField(default=True, verbose_name="Activo")
    
    # Auditoría
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Creado")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Actualizado")

    class Meta:
        verbose_name = "Configuración de la Empresa"
        verbose_name_plural = "Configuraciones de la Empresa"
        ordering = ['code', 'name']
        permissions = [
            ("can_view_all_companies", "Puede ver todas las compañías"),
            ("can_switch_company", "Puede cambiar de compañía"),
        ]

    def __str__(self):
        return f"{self.code} - {self.name}"

    def clean(self):
        """Validaciones personalizadas"""
        if self.is_main:
            existing = Company.objects.filter(is_main=True).exclude(pk=self.pk)
            if existing.exists():
                raise ValidationError("Ya existe una compañía principal. Desactiva la otra primero.")
        
        if self.is_main and self.parent:
            raise ValidationError("La compañía principal no puede tener una compañía padre.")
        
        if self.parent and self.parent.pk == self.pk:
            raise ValidationError("Una compañía no puede ser su propio padre.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    @classmethod
    def get_active(cls):
        """Obtener la compañía activa del sistema."""
        main = cls.objects.filter(is_main=True, is_active=True).first()
        if main:
            return main
        first = cls.objects.filter(is_active=True).first()
        return first

    @classmethod
    def get_main_company(cls):
        """Obtener la compañía principal (matriz)"""
        return cls.objects.filter(is_main=True, is_active=True).first()

    @classmethod
    def get_active_companies(cls):
        """Obtener todas las compañías activas"""
        return cls.objects.filter(is_active=True)

    def get_children(self):
        """Obtener las compañías hijas (sucursales)"""
        return Company.objects.filter(parent=self, is_active=True)

    def get_all_children(self, include_self=True):
        """Obtener todas las compañías hijas de forma recursiva"""
        companies = [self] if include_self else []
        for child in self.get_children():
            companies.extend(child.get_all_children(include_self=True))
        return companies


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
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        verbose_name="Compañía/Sucursal",
        related_name='backups'
    )
    
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
    """✅ MONEDA GLOBAL - Compartida por todas las compañías"""
    
    code = models.CharField(max_length=10, unique=True, verbose_name="Código")  # ← unique=True
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
        indexes = [
            models.Index(fields=['code']),
            models.Index(fields=['is_base']),
        ]

    def __str__(self):
        return f"{self.code} - {self.symbol}"

    def save(self, *args, **kwargs):
        if self.is_base:
            # ✅ Solo una moneda base GLOBAL
            Currency.objects.filter(is_base=True).exclude(pk=self.pk).update(is_base=False)
        super().save(*args, **kwargs)
    
    @classmethod
    def get_base(cls):
        """Obtener moneda base global"""
        return cls.objects.filter(is_base=True).first()


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


class PaymentMethod(models.Model):
    """✅ MÉTODO DE PAGO POR COMPAÑÍA - Cada compañía tiene sus propios métodos"""
    
    name = models.CharField(max_length=100, verbose_name="Nombre")
    code = models.CharField(max_length=20, verbose_name="Código")
    description = models.TextField(blank=True, verbose_name="Descripción")
    
    requires_company_bank = models.BooleanField(
        default=False,
        verbose_name="¿Requiere cuenta bancaria de la empresa?",
        help_text="Marcar si este método usa una cuenta de la empresa (transferencias, cheques)"
    )
    
    requires_reference = models.BooleanField(
        default=False,
        verbose_name="¿Requiere referencia?",
        help_text="Marcar si este método requiere un número de referencia"
    )
    
    requires_approval = models.BooleanField(
        default=False,
        verbose_name="Requiere aprobación",
        help_text="Ej: Cheques, transferencias bancarias"
    )

    default_currency = models.ForeignKey(
        'configuration.Currency',  # ← Global
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        verbose_name="Moneda por defecto"
    )

    icon = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="Icono"
    )
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        verbose_name="Compañía/Sucursal",
        related_name='paymentmethod'
    )
    is_active = models.BooleanField(default=True, verbose_name="Activo")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    history = HistoricalRecords()
    
    class Meta:
        verbose_name = "Método de Pago"
        verbose_name_plural = "Métodos de Pago"
        ordering = ['company__code', 'name']
        unique_together = [['company', 'code']]
        indexes = [
            models.Index(fields=['company', 'code']),
        ]

    def __str__(self):
        return f"{self.name} ({self.company.code})"


class CompanyBankAccount(models.Model):
    """Cuenta bancaria de la empresa (para pagos a proveedores)"""
    
    bank_name = models.CharField(max_length=200, verbose_name="Banco")
    account_number = models.CharField(max_length=50, verbose_name="Número de cuenta")
    account_holder = models.CharField(max_length=200, verbose_name="Titular de la cuenta")
    account_type = models.CharField(
        max_length=20,
        choices=[
            ('CHECKING', 'Cuenta Corriente'),
            ('SAVINGS', 'Cuenta de Ahorro'),
        ],
        default='CHECKING',
        verbose_name="Tipo de cuenta"
    )
    
    currency = models.ForeignKey(
        'configuration.Currency',  # ← Global
        on_delete=models.PROTECT,
        verbose_name="Moneda"
    )
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        verbose_name="Compañía/Sucursal",
        related_name='companybankaccount'
    )
    
    is_default = models.BooleanField(
        default=False,
        verbose_name="¿Cuenta por defecto?"
    )
    
    is_active = models.BooleanField(default=True, verbose_name="Activo")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    history = HistoricalRecords()
    
    class Meta:
        verbose_name = "Cuenta Bancaria de la Empresa"
        verbose_name_plural = "Cuentas Bancarias de la Empresa"
        ordering = ['bank_name', 'account_number']
        unique_together = [['company', 'bank_name', 'account_number']]
        indexes = [
            models.Index(fields=['company', 'is_default']),
        ]
    
    def __str__(self):
        default_mark = " (⭐ Por defecto)" if self.is_default else ""
        return f"{self.bank_name} - {self.account_number}{default_mark}"
    
    def save(self, *args, **kwargs):
        if self.is_default:
            CompanyBankAccount.objects.filter(is_default=True).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)
    
    @classmethod
    def get_default(cls, company=None):
        """Obtener la cuenta por defecto de una compañía"""
        if company is None:
            from .models import Company
            company = Company.get_active()
        if company:
            return cls.objects.filter(is_default=True, is_active=True, company=company).first()
        return None