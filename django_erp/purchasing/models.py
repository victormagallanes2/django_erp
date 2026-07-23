# django_erp/purchasing/models.py
from django.db import models
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from simple_history.models import HistoricalRecords
from decimal import Decimal
from django_erp.configuration.models import Company, Currency, ExchangeRate

User = get_user_model()


class Supplier(models.Model):
    """Proveedor - Similar a Customer"""
    
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
    history = HistoricalRecords()

    class Meta:
        verbose_name = "Proveedor"
        verbose_name_plural = "Proveedores"
        ordering = ['name']
        permissions = [
            ("can_view_supplier", "Puede ver proveedores"),
            ("can_edit_supplier", "Puede editar proveedores"),
            ("can_delete_supplier", "Puede eliminar proveedores"),
        ]

    def __str__(self):
        return f"{self.name} ({self.tax_id})"


class PurchaseOrder(models.Model):
    """Orden de Compra - Igual que Invoice de invoicing"""
    
    STATUS_CHOICES = [
        ('DRAFT', 'Borrador'),
        ('ORDERED', 'Ordenada'),
        ('RECEIVED', 'Recibida'),
        ('CANCELLED', 'Cancelada'),
    ]
    
    number = models.CharField(max_length=50, unique=True, verbose_name="Número")
    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.PROTECT,
        verbose_name="Proveedor"
    )
    date = models.DateField(auto_now_add=True, verbose_name="Fecha")
    expected_delivery = models.DateField(
        null=True, 
        blank=True,
        verbose_name="Fecha esperada de entrega"
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='DRAFT',
        verbose_name="Estado"
    )
    
    # ✅ Totales - Todos como DecimalField
    subtotal = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=Decimal('0.00'), 
        verbose_name="Subtotal"
    )
    tax_rate = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=Decimal('16.00'),  # ✅ Decimal, no float
        verbose_name="Tasa IVA (%)"
    )
    tax = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=Decimal('0.00'), 
        verbose_name="IVA"
    )
    total = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=Decimal('0.00'), 
        verbose_name="Total"
    )
    
    note = models.TextField(blank=True, verbose_name="Nota")
    user = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        verbose_name="Usuario"
    )
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Creado")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Actualizado")
    history = HistoricalRecords()

    class Meta:
        verbose_name = "Orden de Compra"
        verbose_name_plural = "Órdenes de Compra"
        ordering = ['-date', '-created_at']
        permissions = [
            ("can_view_purchaseorder", "Puede ver órdenes de compra"),
            ("can_edit_purchaseorder", "Puede editar órdenes de compra"),
            ("can_delete_purchaseorder", "Puede eliminar órdenes de compra"),
            ("can_confirm_order", "Puede confirmar órdenes de compra"),
            ("can_receive_order", "Puede recibir órdenes de compra"),
            ("can_cancel_order", "Puede cancelar órdenes de compra"),
        ]

    def __str__(self):
        return f"{self.number} - {self.supplier.name}"

    def calculate_totals(self):
	    """Calcular totales - Igual que invoicing"""
	    # ✅ Solo calcular si ya tiene ID
	    if not self.pk:
	        return
	    
	    # ✅ Obtener subtotal
	    subtotal = Decimal('0.00')
	    for line in self.lines.all():
	        subtotal += line.subtotal
	    
	    # ✅ Calcular impuestos
	    tax_rate = Decimal(str(self.tax_rate))
	    tax = subtotal * (tax_rate / Decimal('100'))
	    total = subtotal + tax
	    
	    self.subtotal = subtotal
	    self.tax = tax
	    self.total = total
	    
	    return subtotal, tax, total

    def save(self, *args, **kwargs):
	    """Guardar - Igual que invoicing"""
	    # ✅ Si es nueva orden, establecer tasa de IVA desde la empresa
	    if not self.pk:
	        if not self.tax_rate or self.tax_rate == 0:
	            company = Company.get_active()
	            if company:
	                self.tax_rate = Decimal(str(company.tax_rate))
	            else:
	                self.tax_rate = Decimal('16.00')
	    
	    # ✅ Guardar normalmente
	    super().save(*args, **kwargs)


class PurchaseLine(models.Model):
    """Línea de compra - Igual que InvoiceLine de invoicing"""
    
    order = models.ForeignKey(
        PurchaseOrder,
        on_delete=models.CASCADE,
        related_name='lines',
        verbose_name="Orden de Compra"
    )
    
    # Producto (opcional)
    product = models.ForeignKey(
        'warehouse.Product',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Producto"
    )
    
    # Ubicación sugerida para el producto al recibirlo
    location = models.ForeignKey(
        'warehouse.Location',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Ubicación",
        help_text="Ubicación sugerida para el producto en el almacén"
    )
    
    # ✅ Campos para producto/servicio - Igual que invoicing
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
        help_text="Ejemplo: 'Laptop HP 15.6' o 'Consultoría'"
    )
    
    description = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="Descripción",
        help_text="Detalle adicional (opcional)"
    )
    
    quantity = models.IntegerField(default=1, verbose_name="Cantidad")
    unit_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),  # ✅ Decimal
        verbose_name="Precio unitario"
    )
    subtotal = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        editable=False,
        default=Decimal('0.00'),  # ✅ Decimal
        verbose_name="Subtotal"
    )
    
    history = HistoricalRecords()

    class Meta:
        verbose_name = "Línea de Compra"
        verbose_name_plural = "Líneas de Compra"

    def __str__(self):
        if self.product:
            return f"{self.order.number} - {self.product.name}"
        return f"{self.order.number} - {self.product_name or 'Producto sin nombre'}"

    def save(self, *args, **kwargs):
        # ✅ Si hay producto, guardar nombre y código - Igual que invoicing
        if self.product:
            self.product_code = self.product.code
            self.product_name = self.product.name
        
        # ✅ Si NO hay producto pero hay código, buscar el producto
        elif self.product_code:
            from django_erp.warehouse.models import Product
            try:
                product = Product.objects.get(code=self.product_code)
                self.product = product
                self.product_name = product.name
            except Product.DoesNotExist:
                pass
        
        # Validar valores nulos
        if self.quantity is None:
            self.quantity = 0
        if self.unit_price is None:
            self.unit_price = Decimal('0.00')
        
        # Calcular subtotal
        self.subtotal = Decimal(str(self.quantity)) * Decimal(str(self.unit_price))
        
        # Si no hay nombre pero hay código, usar el código como nombre
        if not self.product_name and self.product_code:
            self.product_name = self.product_code
        
        super().save(*args, **kwargs)