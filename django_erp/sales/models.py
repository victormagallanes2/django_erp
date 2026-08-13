# sales/models.py
from django.db import models
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from simple_history.models import HistoricalRecords
from decimal import Decimal
from django.apps import apps
import uuid
from django.conf import settings
from django_erp.configuration.models import Currency, ExchangeRate, Company



User = get_user_model()


class Customer(models.Model):
    """Cliente - Independiente"""
    
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
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        verbose_name="Compañía/Sucursal",
        related_name='customer'
    )
    history = HistoricalRecords()

    class Meta:
        verbose_name = "Cliente"
        verbose_name_plural = "Clientes"
        ordering = ['name']
        permissions = [
            ("can_view_customer", "Puede ver clientes"),
            ("can_edit_customer", "Puede editar clientes"),
            ("can_delete_customer", "Puede eliminar clientes"),
        ]

    def __str__(self):
        return f"{self.name} ({self.tax_id})"


class SaleOrder(models.Model):
    """Orden de venta"""

    # UUID
    uuid = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
        db_index=True,
        verbose_name="ID Universal"
    )
    
    # Estado de sincronización
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
        verbose_name="Estado de sincronización"
    )
    
    device_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name="Dispositivo de creación"
    )
    
    created_at_local = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Creado localmente"
    )

    # ✅ NUEVO: Campos de fechas para seguimiento
    confirmed_date = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Fecha de Confirmación"
    )
    delivered_date = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Fecha de Entrega"
    )

    STATUS_CHOICES = [
        ('DRAFT', 'Borrador'),
        ('CONFIRMED', 'Confirmada'),
        ('DELIVERED', 'Entregada'),
        ('CANCELLED', 'Cancelada'),
    ]
    
    number = models.CharField(max_length=50, unique=True, verbose_name="Número")
    customer = models.ForeignKey(
        Customer,
        on_delete=models.PROTECT,
        verbose_name="Cliente"
    )
    date = models.DateField(auto_now_add=True, verbose_name="Fecha")
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='DRAFT',
        verbose_name="Estado"
    )
    
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0, editable=False, verbose_name="Subtotal")
    tax = models.DecimalField(max_digits=10, decimal_places=2, default=0, editable=False, verbose_name="Impuesto")
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0, editable=False, verbose_name="Total")
    
    note = models.TextField(blank=True, verbose_name="Nota")
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name="Usuario")
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Creado")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Actualizado")
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        verbose_name="Compañía/Sucursal",
        related_name='saleorder'
    )
    history = HistoricalRecords()

    class Meta:
        verbose_name = "Orden de Venta"
        verbose_name_plural = "Órdenes de Venta"
        ordering = ['-date', '-created_at']
        permissions = [
            ("can_view_saleorder", "Puede ver órdenes de venta"),
            ("can_edit_saleorder", "Puede editar órdenes de venta"),
            ("can_delete_saleorder", "Puede eliminar órdenes de venta"),
            ("can_confirm_order", "Puede confirmar órdenes de venta"),
            ("can_cancel_order", "Puede cancelar órdenes de venta"),
            ("can_deliver_order", "Puede entregar órdenes de venta"),
            ("can_view_reports", "Puede ver reportes de ventas"),
        ]

    def __str__(self):
        return f"{self.number} - {self.customer.name}"

    def calculate_totals(self):
        """Calcular totales usando el IVA de la empresa"""
        from decimal import Decimal, ROUND_HALF_UP
        from django_erp.configuration.models import Company
        
        subtotal = Decimal('0.00')
        for line in self.lines.all():
            subtotal += Decimal(str(line.subtotal))
        
        company = Company.get_active()
        if company:
            tax_rate = Decimal(str(company.tax_rate))
        else:
            tax_rate = Decimal('16.00')
        
        tax = subtotal * (tax_rate / Decimal('100'))
        total = subtotal + tax
        
        self.subtotal = subtotal.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        self.tax = tax.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        self.total = total.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        
        return self.subtotal, self.tax, self.total

    def save(self, *args, **kwargs):
        if not self.uuid:
            self.uuid = uuid.uuid4()
        
        super().save(*args, **kwargs)
        
        if self.pk and self.lines.exists():
            self.calculate_totals()
            super().save(update_fields=['subtotal', 'tax', 'total'])


class SaleLine(models.Model):
    """Línea de venta - Producto opcional"""

    uuid = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
        db_index=True,
        verbose_name="ID Universal"
    )

    order = models.ForeignKey(
        SaleOrder,
        on_delete=models.CASCADE,
        related_name='lines',
        verbose_name="Orden"
    )
    
    product = models.ForeignKey(
        'inventory.Product',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Producto",
        help_text="Seleccionar si es un producto físico",
        related_name='sale_line_products'
    )
    
    location = models.ForeignKey(
        'inventory.Location',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Ubicación",
        help_text="Ubicación del producto en el almacén (si aplica)",
        related_name='sale_line_locations'
    )
    
    product_name = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="Nombre del Producto/Servicio",
        help_text="Usar para servicios o cuando no hay producto seleccionado"
    )
    
    location_code = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="Código de Ubicación",
        help_text="Código de ubicación (si aplica)"
    )
    
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
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        verbose_name="Compañía/Sucursal",
        related_name='saleline'
    )
    history = HistoricalRecords()

    class Meta:
        verbose_name = "Línea de Venta"
        verbose_name_plural = "Líneas de Venta"

    def __str__(self):
        if self.product:
            return f"{self.order.number} - {self.product.name}"
        return f"{self.order.number} - {self.product_name or 'Servicio'}"

    def save(self, *args, **kwargs):
        if self.quantity is None:
            self.quantity = 0
        if self.unit_price is None:
            self.unit_price = 0
        
        self.subtotal = self.quantity * self.unit_price
        
        if not self.product_name and self.product:
            self.product_name = self.product.name
        if not self.location_code and self.location:
            self.location_code = self.location.code
        if not self.uuid:
            self.uuid = uuid.uuid4()
        super().save(*args, **kwargs)


class CashRegister(models.Model):
    """Registro de caja - Integrado en Sales"""

    uuid = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
        db_index=True,
        verbose_name="ID Universal"
    )
    
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
        db_index=True,
        verbose_name="Estado de sincronización"
    )

    STATUS_CHOICES = [
        ('OPEN', 'Abierta'),
        ('CLOSED', 'Cerrada'),
        ('APPROVED', 'Aprobada'),
        ('CANCELLED', 'Cancelada'),
    ]
    
    number = models.CharField(
        max_length=50, 
        unique=True, 
        verbose_name="Número",
        editable=True
    )

    user = models.ForeignKey(
        User, 
        on_delete=models.PROTECT, 
        verbose_name="Cajero",
        related_name='cash_registers'
    )
    
    opened_at = models.DateTimeField(auto_now_add=True, verbose_name="Apertura")
    closed_at = models.DateTimeField(null=True, blank=True, verbose_name="Cierre")
    date = models.DateField(auto_now_add=True, verbose_name="Fecha")
    
    initial_amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0,
        verbose_name="Dinero inicial"
    )
    
    total_sales = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0,
        verbose_name="Total ventas"
    )
    total_expenses = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0,
        verbose_name="Total gastos"
    )
    total_withdrawals = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0,
        verbose_name="Total retiros"
    )
    expected_total = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0,
        verbose_name="Total esperado"
    )
    
    counted_total = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        null=True, 
        blank=True,
        verbose_name="Dinero contado"
    )
    
    breakdown = models.JSONField(
        default=dict, 
        blank=True,
        verbose_name="Desglose",
        help_text='{"100": 5, "50": 3, "20": 10}'
    )
    
    difference = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        null=True, 
        blank=True,
        verbose_name="Diferencia"
    )
    
    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES, 
        default='OPEN',
        verbose_name="Estado"
    )
    
    note = models.TextField(blank=True, verbose_name="Notas")
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Creado")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Actualizado")
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        verbose_name="Compañía/Sucursal",
        related_name='cashregister'
    )
    history = HistoricalRecords()

    class Meta:
        verbose_name = "Cierre de Caja"
        verbose_name_plural = "Cierres de Caja"
        ordering = ['-date', '-opened_at']
        permissions = [
            ("can_open_register", "Puede abrir caja"),
            ("can_close_register", "Puede cerrar caja"),
            ("can_view_register", "Puede ver cierres de caja"),
        ]

        indexes = [
            models.Index(fields=['uuid']),
            models.Index(fields=['sync_status']),
        ]

    def __str__(self):
        return f"{self.number} - {self.user.username} - {self.date}"

    def calculate_totals(self):
        """Calcular totales de la caja"""
        from django.db.models import Sum
        
        total_sales = self.transactions.filter(
            type='SALE'
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        total_expenses = self.transactions.filter(
            type='EXPENSE'
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        total_withdrawals = self.transactions.filter(
            type='WITHDRAWAL'
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        self.total_sales = total_sales
        self.total_expenses = total_expenses
        self.total_withdrawals = total_withdrawals
        self.expected_total = (
            self.initial_amount + 
            self.total_sales - 
            self.total_expenses - 
            self.total_withdrawals
        )
        
        super().save(update_fields=[
            'total_sales', 'total_expenses', 
            'total_withdrawals', 'expected_total'
        ])
        
        return self.expected_total

    def close(self, counted_total, breakdown=None, note=''):
        if self.status != 'OPEN':
            raise ValidationError("Solo se puede cerrar una caja abierta")
        
        from django.utils import timezone
        
        self.calculate_totals()
        
        self.counted_total = counted_total
        self.breakdown = breakdown or {}
        self.difference = self.expected_total - counted_total
        self.closed_at = timezone.now()
        self.status = 'CLOSED'
        
        if note:
            self.note = note
        
        self.save()
        return self.difference

    def save(self, *args, **kwargs):
        if not self.number:
            from datetime import datetime
            date_str = datetime.now().strftime('%Y%m%d')
            last = CashRegister.objects.filter(
                number__startswith=f'CAJA-{date_str}'
            ).order_by('number').last()
            
            if last:
                try:
                    last_num = int(last.number.split('-')[-1])
                    next_num = last_num + 1
                except (ValueError, IndexError):
                    next_num = 1
            else:
                next_num = 1
            
            self.number = f'CAJA-{date_str}-{next_num:04d}'
        
        if self.status == 'OPEN':
            existing_open = CashRegister.objects.filter(
                user=self.user,
                status='OPEN'
            ).exclude(pk=self.pk).exists()
            
            if existing_open:
                raise ValidationError(
                    f"❌ El usuario {self.user.username} ya tiene una caja abierta. "
                    "Debe cerrarla antes de abrir una nueva."
                )
        
        super().save(*args, **kwargs)


class CashTransaction(models.Model):
    """Transacción de caja"""
    
    uuid = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
        db_index=True,
        verbose_name="ID Universal"
    )
    
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
        db_index=True,
        verbose_name="Estado de sincronización"
    )
    
    device_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name="Dispositivo de creación"
    )
    
    created_at_local = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        verbose_name="Creado localmente"
    )

    TYPE_CHOICES = [
        ('SALE', 'Venta'),
        ('EXPENSE', 'Gasto'),
        ('WITHDRAWAL', 'Retiro'),
        ('DEPOSIT', 'Depósito'),
        ('ADJUSTMENT', 'Ajuste'),
    ]
    
    register = models.ForeignKey(
        CashRegister, 
        on_delete=models.CASCADE, 
        related_name='transactions',
        verbose_name="Caja"
    )
    type = models.CharField(
        max_length=20, 
        choices=TYPE_CHOICES,
        verbose_name="Tipo"
    )
    amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        verbose_name="Monto"
    )
    description = models.CharField(
        max_length=200,
        verbose_name="Descripción"
    )
    reference = models.CharField(
        max_length=100, 
        blank=True,
        verbose_name="Referencia"
    )
    user = models.ForeignKey(
        User, 
        on_delete=models.PROTECT,
        verbose_name="Usuario"
    )
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        verbose_name="Compañía/Sucursal",
        related_name='cashtransaction'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Creado"
    )

    class Meta:
        verbose_name = "Transacción de Caja"
        verbose_name_plural = "Transacciones de Caja"
        ordering = ['-created_at']

        indexes = [
            models.Index(fields=['uuid']),
            models.Index(fields=['sync_status']),
        ]

    def __str__(self):
        if not self.uuid:
            self.uuid = uuid.uuid4()
        return f"{self.get_type_display()} - {self.amount} - {self.description}"


class Payment(models.Model):
    """Pago de cliente (ventas) - Solo registra lo que el cliente paga"""
    
    sale_order = models.ForeignKey(
        'sales.SaleOrder',
        on_delete=models.CASCADE,
        related_name='payments',
        verbose_name="Orden de Venta",
        null=True,  # ✅ Permitir null
        blank=True,  # ✅ Permitir blank en formularios
        help_text="Orden de venta a la que pertenece este pago (opcional)."
    )

    sale_invoice = models.ForeignKey(
        'sales.SaleInvoice',
        on_delete=models.CASCADE,
        related_name='payments',
        verbose_name="Factura de Venta",
        null=True,
        blank=True,  # Para compatibilidad con pagos existentes
        help_text="Factura a la que pertenece este pago."
    )
    
    method = models.ForeignKey(
        'configuration.PaymentMethod',
        on_delete=models.PROTECT,
        verbose_name="Método de Pago"
    )

    currency = models.ForeignKey(
        'configuration.Currency',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        verbose_name="Moneda"
    )

    amount = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        verbose_name="Monto"
    )

    amount_usd = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        editable=False,
        default=0,
        verbose_name="Monto en USD"
    )

    reference = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Referencia"
    )
    
    customer_bank = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="Banco del cliente",
        help_text="Banco desde el cual el cliente realizó el pago"
    )
    
    STATUS_CHOICES = [
        ('PENDING', 'Pendiente'),
        ('COMPLETED', 'Completado'),
        ('FAILED', 'Fallido'),
        ('CANCELLED', 'Cancelado'),
    ]
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='PENDING',
        verbose_name="Estado"
    )
    
    payment_date = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Pago")
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name="Usuario"
    )
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        verbose_name="Compañía/Sucursal",
        related_name='payments'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    history = HistoricalRecords()
    
    class Meta:
        verbose_name = "Pago de Venta"
        verbose_name_plural = "Pagos de Ventas"
        ordering = ['-payment_date']

    def __str__(self):
        """Representación del pago"""
        # ✅ Si tiene orden de venta
        if self.sale_order:
            return f"{self.sale_order.number} - {self.method.name} - {self.amount}"
        # ✅ Si tiene factura
        elif self.sale_invoice:
            return f"{self.sale_invoice.number} - {self.method.name} - {self.amount}"
        # ✅ Si no tiene referencia
        else:
            return f"Pago #{self.id} - {self.method.name} - {self.amount}"

    def save(self, *args, **kwargs):
        from django_erp.configuration.models import Currency, ExchangeRate
        from decimal import Decimal, ROUND_HALF_UP
        
        if not self.currency_id and self.method_id:
            if self.method.default_currency:
                self.currency = self.method.default_currency
            else:
                usd = Currency.objects.get(code='USD')
                self.currency = usd
        
        if not self.currency_id:
            usd = Currency.objects.get(code='USD')
            self.currency = usd
        
        if self.currency.code == 'USD':
            self.amount_usd = self.amount
        else:
            rate = ExchangeRate.get_today_rate(self.currency.code, 'USD')
            if rate and rate > 0:
                self.amount_usd = (self.amount / Decimal(str(rate))).quantize(
                    Decimal('0.01'), rounding=ROUND_HALF_UP
                )
            else:
                self.amount_usd = self.amount
        
        super().save(*args, **kwargs)


class SaleInvoice(models.Model):
    """Factura de Venta"""
    
    # UUID
    uuid = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
        db_index=True,
        verbose_name="ID Universal"
    )
    
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
        db_index=True,
        verbose_name="Estado de sincronización"
    )
    
    device_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name="Dispositivo de creación"
    )
    
    created_at_local = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        verbose_name="Creado localmente"
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
    
    # Estados de factura
    STATUS_CHOICES = [
        ('DRAFT', 'Borrador'),
        ('ISSUED', 'Emitida'),
        ('PAID', 'Pagada'),
        ('CANCELLED', 'Anulada'),
    ]
    
    # Número de factura
    number = models.CharField(max_length=50, unique=True, verbose_name="Número de Factura")
    
    # Relación con la orden de venta
    sale_order = models.ForeignKey(
        'sales.SaleOrder',
        on_delete=models.SET_NULL,  # ✅ Cambiar a SET_NULL
        related_name='invoices',
        verbose_name="Orden de Venta",
        null=True,
        blank=True  # ✅ Permitir null
    )
    
    # Cliente
    customer = models.ForeignKey(
        'sales.Customer',
        on_delete=models.PROTECT,
        verbose_name="Cliente"
    )
    
    # Datos del cliente (copia)
    customer_name = models.CharField(
        max_length=200,
        verbose_name="Nombre del Cliente"
    )
    customer_tax_id = models.CharField(
        max_length=20,
        verbose_name="RIF / Cédula del Cliente"
    )
    customer_address = models.TextField(
        blank=True,
        verbose_name="Dirección del Cliente"
    )
    
    # Fechas
    date_issued = models.DateField(auto_now_add=True, verbose_name="Fecha de Emisión")
    date_due = models.DateField(
        null=True,
        blank=True,
        verbose_name="Fecha de Vencimiento"
    )
    
    # Estado
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='DRAFT',
        verbose_name="Estado"
    )
    
    # Totales
    subtotal = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0, 
        verbose_name="Subtotal"
    )
    tax_rate = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=16.00, 
        verbose_name="Tasa IVA (%)"
    )
    tax = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0, 
        verbose_name="IVA"
    )
    total = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0, 
        verbose_name="Total"
    )
    
    # Observaciones
    note = models.TextField(blank=True, verbose_name="Nota")
    user = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        verbose_name="Usuario"
    )
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        verbose_name="Compañía/Sucursal",
        related_name='sale_invoices'
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Creado")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Actualizado")
    history = HistoricalRecords()

    class Meta:
        verbose_name = "Factura de Venta"
        verbose_name_plural = "Facturas de Venta"
        ordering = ['-date_issued', '-created_at']
        permissions = [
            ("can_view_saleinvoice", "Puede ver facturas de venta"),
            ("can_edit_saleinvoice", "Puede editar facturas de venta"),
            ("can_delete_saleinvoice", "Puede eliminar facturas de venta"),
            ("can_issue_saleinvoice", "Puede emitir facturas de venta"),
            ("can_pay_saleinvoice", "Puede pagar facturas de venta"),
            ("can_cancel_saleinvoice", "Puede anular facturas de venta"),
        ]

    def __str__(self):
        return f"{self.number} - {self.customer_name if self.customer_name else self.customer.name if self.customer else 'Sin cliente'}"

    def calculate_totals(self):
        """Calcular totales usando el IVA de la empresa"""
        from decimal import Decimal, ROUND_HALF_UP
        from django_erp.configuration.models import Company
        
        subtotal = sum(line.subtotal for line in self.lines.all())
        
        company = Company.get_active()
        if company:
            tax_rate = Decimal(str(company.tax_rate))
        else:
            tax_rate = Decimal('16.00')
        
        tax = subtotal * (tax_rate / Decimal('100'))
        total = subtotal + tax
        
        self.subtotal = subtotal.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        self.tax = tax.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        self.total = total.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        
        return self.subtotal, self.tax, self.total

    def save(self, *args, **kwargs):
        if not self.uuid:
            self.uuid = uuid.uuid4()
        
        if self.sale_order and self.sale_order.customer:
            self.customer = self.sale_order.customer
            self.customer_name = self.sale_order.customer.name
            self.customer_tax_id = self.sale_order.customer.tax_id
            self.customer_address = self.sale_order.customer.address
        
        super().save(*args, **kwargs)
        
        if self.pk and self.lines.exists():
            self.calculate_totals()
            super().save(update_fields=['subtotal', 'tax', 'total'])


class SaleInvoiceLine(models.Model):
    """Línea de Factura de Venta"""
    
    uuid = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
        db_index=True,
        verbose_name="ID Universal"
    )
    
    invoice = models.ForeignKey(
        SaleInvoice,
        on_delete=models.CASCADE,
        related_name='lines',
        verbose_name="Factura de Venta"
    )
    
    # Relación con la línea de venta original
    sale_line = models.ForeignKey(
        'sales.SaleLine',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Línea de Venta Original"
    )
    
    # Producto (opcional)
    product = models.ForeignKey(
        'inventory.Product',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Producto"
    )
    
    # Datos del producto (copia)
    product_code = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="Código de Producto"
    )
    product_name = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="Nombre del Producto/Servicio"
    )
    description = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="Descripción"
    )
    
    # Cantidad y precios
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
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        verbose_name="Compañía/Sucursal",
        related_name='sale_invoice_lines'
    )
    history = HistoricalRecords()

    class Meta:
        verbose_name = "Línea de Factura de Venta"
        verbose_name_plural = "Líneas de Factura de Venta"

    def __str__(self):
        return f"{self.invoice.number} - {self.product_name or self.product_code or 'Sin producto'}"

    def save(self, *args, **kwargs):
        if self.sale_line:
            if self.sale_line.product:
                self.product = self.sale_line.product
                self.product_code = self.sale_line.product.code
                self.product_name = self.sale_line.product.name
            else:
                self.product_name = self.sale_line.product_name
                self.product_code = self.sale_line.product_code
            self.quantity = self.sale_line.quantity
            self.unit_price = self.sale_line.unit_price
            self.description = self.sale_line.description or self.product_name
        
        if not self.uuid:
            self.uuid = uuid.uuid4()
        
        self.subtotal = self.quantity * self.unit_price
        super().save(*args, **kwargs)