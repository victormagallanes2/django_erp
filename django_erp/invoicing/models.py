# invoicing/models.py
from django.db import models
from django.contrib.auth import get_user_model
from decimal import Decimal
from django_erp.configuration.models import Company

User = get_user_model()


class Invoice(models.Model):
    """Factura"""
    
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
        help_text="Asignado por la imprenta digital autorizada (si aplica)"
    )
    
    # Datos de la empresa
    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        verbose_name="Empresa",
        help_text="Datos de la empresa que emite la factura"
    )
    issuer_rif = models.CharField(max_length=20, verbose_name="RIF Emisor")
    issuer_name = models.CharField(max_length=200, verbose_name="Nombre Emisor")
    issuer_address = models.TextField(verbose_name="Dirección Emisor")
    
    # Datos del cliente
    customer = models.ForeignKey('sales.Customer', on_delete=models.PROTECT, verbose_name="Cliente")
    customer_rif = models.CharField(max_length=20, verbose_name="RIF Cliente")
    customer_address = models.TextField(verbose_name="Dirección Cliente")
    
    # Datos de la factura
    sale_order = models.OneToOneField(
        'sales.SaleOrder',
        on_delete=models.PROTECT,
        related_name='invoice',
        null=True,
        blank=True,
        verbose_name="Orden de Venta"
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
    
    # Información adicional
    note = models.TextField(blank=True, verbose_name="Nota")
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name="Usuario")
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Creado")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Actualizado")

    class Meta:
        verbose_name = "Factura"
        verbose_name_plural = "Facturas"
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f"{self.number} - {self.customer.name}"

    def calculate_totals(self):
        subtotal = sum(line.subtotal for line in self.lines.all())
        tax = subtotal * (self.tax_rate / Decimal('100'))
        total = subtotal + tax
        
        self.subtotal = subtotal
        self.tax = tax
        self.total = total
        return subtotal, tax, total


class InvoiceLine(models.Model):
    """Línea de factura"""
    
    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.CASCADE,
        related_name='lines',
        verbose_name="Factura"
    )
    product = models.ForeignKey(
        'warehouse.Product',
        on_delete=models.PROTECT,
        verbose_name="Producto"
    )
    description = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="Descripción"
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
        return f"{self.invoice.number} - {self.product.name}"

    def save(self, *args, **kwargs):
        self.subtotal = self.quantity * self.unit_price
        if not self.description:
            self.description = self.product.name
        super().save(*args, **kwargs)