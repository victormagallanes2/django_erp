# sales/models.py
from django.db import models
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from decimal import Decimal 


User = get_user_model()


class Customer(models.Model):
    """Cliente - Datos de negocio"""
    
    name = models.CharField(max_length=200, verbose_name="Nombre")
    tax_id = models.CharField(
        max_length=20,
        unique=True,
        verbose_name="RIF / Cédula",
        help_text="Persona Natural: V-12345678 | Empresa: J-12345678-9"
    )
    email = models.EmailField(blank=True, null=True, verbose_name="Email")
    phone = models.CharField(max_length=20, blank=True, verbose_name="Teléfono")
    address = models.TextField(blank=True, verbose_name="Dirección")
    is_active = models.BooleanField(default=True, verbose_name="Activo")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Creado")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Actualizado")

    class Meta:
        verbose_name = "Cliente"
        verbose_name_plural = "Clientes"
        ordering = ['name']

    def __str__(self):
        return self.name


class SaleOrder(models.Model):
    """Orden de venta"""
    
    STATUS_CHOICES = [
        ('DRAFT', 'Borrador'),
        ('CONFIRMED', 'Confirmada'),
        ('DELIVERED', 'Entregada'),
        ('CANCELLED', 'Cancelada'),
    ]
    
    number = models.CharField(max_length=50, unique=True, verbose_name="Número")
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, verbose_name="Cliente")
    date = models.DateField(auto_now_add=True, verbose_name="Fecha")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT', verbose_name="Estado")
    
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0, editable=False, verbose_name="Subtotal")
    tax = models.DecimalField(max_digits=10, decimal_places=2, default=0, editable=False, verbose_name="Impuesto")
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0, editable=False, verbose_name="Total")
    
    note = models.TextField(blank=True, verbose_name="Nota")
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name="Usuario")
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Creado")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Actualizado")

    class Meta:
        verbose_name = "Orden de Venta"
        verbose_name_plural = "Órdenes de Venta"
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f"{self.number} - {self.customer.name}"

    def calculate_totals(self):
        subtotal = sum(line.subtotal for line in self.lines.all())
        tax = subtotal * Decimal('0.19')  # ← Cambiar 0.19 por Decimal('0.19')
        total = subtotal + tax
        
        self.subtotal = subtotal
        self.tax = tax
        self.total = total
        return subtotal, tax, total

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.calculate_totals()
        super().save(*args, **kwargs)


class SaleLine(models.Model):
    """Línea de orden de venta - CON REFERENCIAS DINÁMICAS"""
    
    order = models.ForeignKey(
        SaleOrder,
        on_delete=models.CASCADE,
        related_name='lines',
        verbose_name="Orden"
    )
    
    # ✅ REFERENCIAS DINÁMICAS a warehouse
    product = models.ForeignKey(
        'warehouse.Product',  # ← Texto, no importación directa
        on_delete=models.PROTECT,
        verbose_name="Producto"
    )
    location = models.ForeignKey(
        'warehouse.Location',  # ← Texto, no importación directa
        on_delete=models.SET_NULL,
        null=True,
        verbose_name="Ubicación"
    )
    
    quantity = models.IntegerField(verbose_name="Cantidad")
    unit_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Precio unitario"
    )
    subtotal = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        editable=False,
        verbose_name="Subtotal"
    )

    class Meta:
        verbose_name = "Línea de Venta"
        verbose_name_plural = "Líneas de Venta"

    def __str__(self):
        return f"{self.order.number} - {self.product.name}"

    def save(self, *args, **kwargs):
        self.subtotal = self.quantity * self.unit_price
        super().save(*args, **kwargs)