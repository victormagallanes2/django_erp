# invoicing/models.py
from django.db import models
from django.contrib.auth import get_user_model
from decimal import Decimal
from django_erp.configuration.models import Company
from simple_history.models import HistoricalRecords
import uuid

User = get_user_model()


class Invoice(models.Model):
    """Factura - Completamente independiente"""
    
    # ✅ UUID con db_index=True (el índice se crea con el campo)
    uuid = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
        db_index=True,  # ← ✅ ESTO CREA EL ÍNDICE AUTOMÁTICAMENTE
        verbose_name="ID Universal"
    )
    
    # ✅ Estado de sincronización (también con índice)
    SYNC_STATUS_CHOICES = [
        ('PENDING', 'Pendiente de sincronizar'),
        ('SYNCING', 'Sincronizando...'),
        ('SYNCED', 'Sincronizada'),
        ('FAILED', 'Error en sincronización'),
    ]
    
    sync_status = models.CharField(
        max_length=20,
        choices=SYNC_STATUS_CHOICES,
        default='PENDING',
        db_index=True,  # ← ✅ ÍNDICE PARA BÚSQUEDAS RÁPIDAS
        verbose_name="Estado de sincronización"
    )
    
    # ✅ created_at_local con índice
    created_at_local = models.DateTimeField(
        auto_now_add=True,
        db_index=True,  # ← ✅ ÍNDICE PARA ORDENAR
        verbose_name="Creado localmente"
    )
    
    device_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name="Dispositivo de creación",
        help_text="Identificador del equipo que creó la factura"
    )
    
    synced_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Sincronizado el"
    )
    
    sync_attempts = models.IntegerField(
        default=0,
        verbose_name="Intentos de sincronización"
    )
    
    sync_error = models.TextField(
        blank=True,
        verbose_name="Error de sincronización"
    )

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

    customer = models.ForeignKey(
        'sales.Customer',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Cliente"
    )
    
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

    payment_summary = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Resumen de Pagos",
        help_text='{"CASH": 300, "CREDIT_CARD": 200}'
    )
    
    # ✅ NUEVO: Monto total pagado
    paid_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name="Monto Pagado"
    )
    
    # ✅ NUEVO: Cambio (si aplica)
    change_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name="Cambio"
    )

   # ✅ NUEVO: Vuelto por moneda
    change_summary = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Vuelto por Moneda",
        help_text='{"USD": 20, "BS": 500}'
    )

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Creado")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Actualizado")
    history = HistoricalRecords()

    class Meta:
        verbose_name = "Factura"
        verbose_name_plural = "Facturas"
        ordering = ['-date', '-created_at']
        permissions = [
            ("can_view_invoice", "Puede ver facturas"),
            ("can_edit_invoice", "Puede editar facturas"),
            ("can_delete_invoice", "Puede eliminar facturas"),
            ("can_issue_invoice", "Puede emitir facturas"),
            ("can_pay_invoice", "Puede pagar facturas"),
            ("can_cancel_invoice", "Puede anular facturas"),
        ]


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

    def save(self, *args, **kwargs):
        # ✅ Si hay un cliente seleccionado, guardar sus datos en los campos de texto
        if self.customer:
            self.customer_name = self.customer.name
            self.customer_rif = self.customer.tax_id
            self.customer_address = self.customer.address
        # ✅ NUEVO: Si es una factura nueva, generar UUID si no tiene
        if not self.uuid:
            self.uuid = uuid.uuid4()
        
        super().save(*args, **kwargs)


class InvoiceLine(models.Model):

    # ✅ NUEVO: UUID para línea de factura
    uuid = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
        db_index=True,
        verbose_name="ID Universal"
    )

    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.CASCADE,
        related_name='lines',
        verbose_name="Factura"
    )

    product = models.ForeignKey(
        'warehouse.Product',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Producto"
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

    def get_formset(self, request, obj=None, **kwargs):
        formset = super().get_formset(request, obj, **kwargs)
        from django_erp.warehouse.models import Product
        formset.form.base_fields['product'].queryset = Product.objects.filter(is_active=True)
        return formset

    history = HistoricalRecords()

    class Meta:
        verbose_name = "Línea de Factura"
        verbose_name_plural = "Líneas de Factura"
        permissions = [
            ("can_view_invoiceline", "Puede ver líneas de factura"),
            ("can_edit_invoiceline", "Puede editar líneas de factura"),
        ]


    def __str__(self):
        name = self.product_name or self.description or 'Sin producto'
        return f"{self.invoice.number} - {name}"

    def save(self, *args, **kwargs):
        # ✅ Si hay producto, guardar nombre y código
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
        
        if self.quantity is None:
            self.quantity = 0
        if self.unit_price is None:
            self.unit_price = 0
        
        self.subtotal = self.quantity * self.unit_price
        
        if not self.product_name and self.product_code:
            self.product_name = self.product_code

        # ✅ NUEVO: Generar UUID si no tiene
        if not self.uuid:
            self.uuid = uuid.uuid4()
        
        super().save(*args, **kwargs)