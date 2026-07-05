# invoicing/models.py
from django.db import models
from django.contrib.auth import get_user_model
from decimal import Decimal
from django_erp.configuration.models import Company

User = get_user_model()


class Invoice(models.Model):
    """Factura - Completamente independiente"""
    
    STATUS_CHOICES = [
        ('DRAFT', 'Borrador'),
        ('ISSUED', 'Emitida'),
        ('PAID', 'Pagada'),
        ('CANCELLED', 'Anulada'),
    ]
    
    # Números
    number = models.CharField(max_length=50, unique=True, verbose_name="Número Interno")
    control_number = models.CharField(
        max_length=50, 
        blank=True, 
        null=True,
        verbose_name="Número de Control SENIAT",
    )
    
    # Datos de la empresa
    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        verbose_name="Empresa"
    )
    issuer_rif = models.CharField(max_length=20, verbose_name="RIF Emisor")
    issuer_name = models.CharField(max_length=200, verbose_name="Nombre Emisor")
    issuer_address = models.TextField(verbose_name="Dirección Emisor")
    
    # ✅ Datos del cliente - Campos separados (en lugar de JSON)
    customer_name = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="Nombre del Cliente",
        help_text="Ejemplo: Juan Pérez"
    )
    customer_rif = models.CharField(
        max_length=20,
        blank=True,
        verbose_name="RIF / Cédula del Cliente",
        help_text="Ejemplo: V-12345678 o J-12345678-9"
    )
    customer_address = models.TextField(
        blank=True,
        verbose_name="Dirección del Cliente",
        help_text="Ejemplo: Calle Falsa 123, Ciudad"
    )
    
    # Referencia a la orden de venta (SOLO texto)
    sale_order_number = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name="Número de Orden de Venta",
        help_text="Referencia a la orden de venta (si aplica)"
    )
    
    # Concepto general
    concept = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="Concepto",
        help_text="Usar si no hay líneas específicas"
    )
    
    date = models.DateField(auto_now_add=True, verbose_name="Fecha")
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='DRAFT',
        verbose_name="Estado"
    )
    
    # Totales
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Subtotal")
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=16.00, verbose_name="Tasa IVA (%)")
    tax = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="IVA")
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Total")
    
    note = models.TextField(blank=True, verbose_name="Nota")
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name="Usuario")
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Creado")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Actualizado")

    class Meta:
        verbose_name = "Factura"
        verbose_name_plural = "Facturas"
        ordering = ['-date', '-created_at']

    def __str__(self):
        if self.customer_name:
            return f"{self.number} - {self.customer_name}"
        return f"{self.number} - {self.concept or 'Sin cliente'}"

    def calculate_totals(self):
        subtotal = sum(line.subtotal for line in self.lines.all())
        tax = subtotal * (self.tax_rate / Decimal('100'))
        total = subtotal + tax
        
        self.subtotal = subtotal
        self.tax = tax
        self.total = total
        return subtotal, tax, total


class InvoiceLine(models.Model):
    """Línea de factura - Con campos separados"""
    
    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.CASCADE,
        related_name='lines',
        verbose_name="Factura"
    )
    
    # Campos para producto/servicio
    product_code = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="Código de Producto",
        help_text="Código del producto (si aplica)"
    )
    product_name = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="Nombre del Producto/Servicio",
        help_text="Ejemplo: 'Laptop HP 15.6' o 'Consultoría jurídica'"
    )
    
    # Descripción adicional
    description = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="Descripción",
        help_text="Detalle adicional (opcional)"
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
        verbose_name = "Línea de Factura"
        verbose_name_plural = "Líneas de Factura"

    def __str__(self):
        name = self.product_name or self.description or 'Sin producto'
        return f"{self.invoice.number} - {name}"

    def save(self, *args, **kwargs):
        self.subtotal = self.quantity * self.unit_price
        if not self.product_name and self.description:
            self.product_name = self.description
        super().save(*args, **kwargs)