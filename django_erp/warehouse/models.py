# warehouse/models.py
from django.db import models
from django.contrib.auth import get_user_model
from simple_history.models import HistoricalRecords
from decimal import Decimal

User = get_user_model()


class Product(models.Model):
    """Producto - Precio en moneda base configurable"""
    
    UNIT_CHOICES = [
        ('UNIT', 'Unidad'),
        ('KG', 'Kilogramo'),
        ('L', 'Litro'),
        ('M', 'Metro'),
    ]
    
    name = models.CharField(max_length=200, verbose_name="Nombre")
    code = models.CharField(max_length=50, unique=True, verbose_name="Código")
    description = models.TextField(blank=True, verbose_name="Descripción")
    unit = models.CharField(max_length=10, choices=UNIT_CHOICES, default='UNIT', verbose_name="Unidad")
    
    # ✅ Precio en moneda base (único campo de precio)
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name="Precio",
        help_text="Precio en la moneda base del sistema (configurable en Configuración → Monedas)"
    )
    
    is_service = models.BooleanField(
        default=False,
        verbose_name="¿Es servicio?",
        help_text="Marcar si es un servicio (no requiere control de stock)"
    )
    
    weight = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="Peso (kg)")
    dimensions = models.CharField(max_length=100, blank=True, verbose_name="Dimensiones (LxAxA)")
    image = models.ImageField(upload_to='products/', blank=True, null=True, verbose_name="Imagen")
    
    is_active = models.BooleanField(default=True, verbose_name="Activo")
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Creado")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Actualizado")
    
    history = HistoricalRecords()

    class Meta:
        verbose_name = "Producto"
        verbose_name_plural = "Productos"
        ordering = ['name']
        permissions = [
            ("can_view_product", "Puede ver productos"),
            ("can_edit_product", "Puede editar productos"),
            ("can_delete_product", "Puede eliminar productos"),
        ]

    def __str__(self):
        return f"{self.code} - {self.name}"
    
    def get_price_in_currency(self, currency_code):
        """Obtener precio en una moneda específica"""
        from configuration.models import Currency, ExchangeRate
        
        base = Currency.get_base()
        if not base:
            return self.price
        
        if currency_code == base.code:
            return self.price
        
        rate = ExchangeRate.get_rate(base.code, currency_code)
        return self.price * rate
    
    def get_price_display(self, currency_code=None):
        """Obtener precio con formato de moneda"""
        from configuration.models import Currency
        if currency_code is None:
            currency = Currency.get_base()
        else:
            currency = Currency.objects.get(code=currency_code)
        
        price = self.get_price_in_currency(currency.code)
        return f"{currency.symbol} {price:.{currency.decimal_places}f}"


class Location(models.Model):
    """Ubicación física en el almacén"""
    
    code = models.CharField(max_length=50, unique=True, verbose_name="Código")
    name = models.CharField(max_length=200, verbose_name="Nombre")
    description = models.TextField(blank=True, verbose_name="Descripción")
    
    parent = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Ubicación padre")
    is_active = models.BooleanField(default=True, verbose_name="Activo")
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Creado")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Actualizado")
    
    history = HistoricalRecords()

    class Meta:
        verbose_name = "Ubicación"
        verbose_name_plural = "Ubicaciones"
        ordering = ['code']

    def __str__(self):
        return f"{self.code} - {self.name}"


class Movement(models.Model):
    """Movimiento FÍSICO - Cambia ubicación de productos"""
    
    TYPE_CHOICES = [
        ('ENTRY', 'Entrada'),
        ('EXIT', 'Salida'),
        ('TRANSFER', 'Traslado'),
        ('ADJUSTMENT', 'Ajuste'),
    ]
    
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='movements', verbose_name="Producto")
    type = models.CharField(max_length=10, choices=TYPE_CHOICES, verbose_name="Tipo")
    quantity = models.IntegerField(verbose_name="Cantidad")
    
    unit_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name="Precio unitario"
    )
    total = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        editable=False,
        verbose_name="Total"
    )
    
    location_from = models.ForeignKey(
        Location,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='movements_from',
        verbose_name="Desde"
    )
    location_to = models.ForeignKey(
        Location,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='movements_to',
        verbose_name="Hasta"
    )
    
    note = models.TextField(blank=True, verbose_name="Nota")
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name="Usuario")
    
    source_type = models.CharField(
        max_length=20,
        choices=[('MANUAL', 'Manual'), ('PURCHASE', 'Compra'), ('SALE', 'Venta')],
        default='MANUAL',
        verbose_name="Tipo de origen"
    )
    source_reference = models.CharField(max_length=100, blank=True, verbose_name="Referencia")
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Creado")
    
    history = HistoricalRecords()

    class Meta:
        verbose_name = "Movimiento"
        verbose_name_plural = "Movimientos"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.get_type_display()} - {self.product.name} - {self.quantity}"

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.quantity <= 0:
            raise ValidationError("La cantidad debe ser mayor a cero")
        
        if self.type == 'TRANSFER' and (not self.location_from or not self.location_to):
            raise ValidationError("Los traslados requieren ubicación de origen y destino")
        
        if self.type == 'TRANSFER' and self.location_from == self.location_to:
            raise ValidationError("Origen y destino no pueden ser la misma ubicación")

    def save(self, *args, **kwargs):
        self.total = self.quantity * self.unit_price
        self.clean()
        super().save(*args, **kwargs)