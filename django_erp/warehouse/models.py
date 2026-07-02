# warehouse/models.py
from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class Product(models.Model):
    """Producto - Solo datos del producto"""
    
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
    
    # Características físicas
    weight = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="Peso (kg)")
    dimensions = models.CharField(max_length=100, blank=True, verbose_name="Dimensiones (LxAxA)")
    
    # Imagen
    image = models.ImageField(upload_to='products/', blank=True, null=True, verbose_name="Imagen")
    
    # Estado
    is_active = models.BooleanField(default=True, verbose_name="Activo")
    
    # Auditoría
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Creado")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Actualizado")

    class Meta:
        verbose_name = "Producto"
        verbose_name_plural = "Productos"
        ordering = ['name']

    def __str__(self):
        return f"{self.code} - {self.name}"


class Location(models.Model):
    """Ubicación física en el almacén"""
    
    code = models.CharField(max_length=50, unique=True, verbose_name="Código")
    name = models.CharField(max_length=200, verbose_name="Nombre")
    description = models.TextField(blank=True, verbose_name="Descripción")
    
    # Jerarquía de ubicaciones
    parent = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Ubicación padre")
    is_active = models.BooleanField(default=True, verbose_name="Activo")
    
    # Auditoría
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Creado")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Actualizado")

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
    
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='movements')
    type = models.CharField(max_length=10, choices=TYPE_CHOICES, verbose_name="Tipo")
    quantity = models.IntegerField(verbose_name="Cantidad")
    
    # Ubicaciones (origen y destino)
    location_from = models.ForeignKey(Location, on_delete=models.SET_NULL, null=True, blank=True, related_name='movements_from', verbose_name="Desde")
    location_to = models.ForeignKey(Location, on_delete=models.SET_NULL, null=True, blank=True, related_name='movements_to', verbose_name="Hasta")
    
    # Metadata
    note = models.TextField(blank=True, verbose_name="Nota")
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name="Usuario")
    
    # Referencia al documento origen
    source_type = models.CharField(max_length=20, choices=[('MANUAL', 'Manual'), ('PURCHASE', 'Compra'), ('SALE', 'Venta')], default='MANUAL')
    source_reference = models.CharField(max_length=100, blank=True, verbose_name="Referencia")
    
    # Auditoría
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Creado")
    unit_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name="Precio unitario",
        help_text="Precio de compra para entradas, precio de venta para salidas"
    )
    total = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        editable=False,
        verbose_name="Total"
    )

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
        if self.type in ['ENTRY', 'EXIT'] and self.unit_price < 0:
                    raise ValidationError("El precio unitario no puede ser negativo")

    def save(self, *args, **kwargs):
        """Calcula el total antes de guardar"""
        self.total = self.quantity * self.unit_price
        self.clean()
        super().save(*args, **kwargs)