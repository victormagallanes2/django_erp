# sales/models.py
from django.db import models
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from simple_history.models import HistoricalRecords
from decimal import Decimal
from django.apps import apps
import uuid


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

    # ✅ NUEVO: UUID
    uuid = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
        db_index=True,
        verbose_name="ID Universal"
    )
    
    # ✅ NUEVO: Estado de sincronización
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
    
    # ✅ NUEVO: Device ID
    device_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name="Dispositivo de creación"
    )
    
    # ✅ NUEVO: Fecha de creación local
    created_at_local = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Creado localmente"
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
        subtotal = sum(line.subtotal for line in self.lines.all())
        tax = subtotal * Decimal('0.19')
        total = subtotal + tax
        
        self.subtotal = subtotal
        self.tax = tax
        self.total = total
        return subtotal, tax, total

    def save(self, *args, **kwargs):
        # ✅ NUEVO: Generar UUID si no tiene
        if not self.uuid:
            self.uuid = uuid.uuid4()
        super().save(*args, **kwargs)
        self.calculate_totals()
        super().save(*args, **kwargs)


class SaleLine(models.Model):
    """Línea de venta - Producto opcional"""

    # ✅ NUEVO: UUID
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
    
    # ✅ Producto como ForeignKey condicional
    product = models.ForeignKey(
        'warehouse.Product',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Producto",
        help_text="Seleccionar si es un producto físico"
    )
    
    # ✅ Ubicación como ForeignKey condicional
    location = models.ForeignKey(
        'warehouse.Location',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Ubicación",
        help_text="Ubicación del producto en el almacén (si aplica)"
    )
    
    # ✅ Para servicios (cuando no hay producto)
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
    
    # ✅ Descripción para servicios
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

    history = HistoricalRecords()

    class Meta:
        verbose_name = "Línea de Venta"
        verbose_name_plural = "Líneas de Venta"


    def __str__(self):
        if self.product:
            return f"{self.order.number} - {self.product.name}"
        return f"{self.order.number} - {self.product_name or 'Servicio'}"

    def save(self, *args, **kwargs):
        # ✅ Validación para evitar None
        if self.quantity is None:
            self.quantity = 0
        if self.unit_price is None:
            self.unit_price = 0
        
        self.subtotal = self.quantity * self.unit_price
        
        if not self.product_name and self.product:
            self.product_name = self.product.name
        if not self.location_code and self.location:
            self.location_code = self.location.code
        # ✅ NUEVO: Generar UUID si no tiene
        if not self.uuid:
            self.uuid = uuid.uuid4()
        super().save(*args, **kwargs)


class CashRegister(models.Model):
    """Registro de caja - Integrado en Sales"""
    
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

    def __str__(self):
        return f"{self.number} - {self.user.username} - {self.date}"

    def calculate_totals(self):
        """Calcular totales de la caja"""
        from django.db.models import Sum
        
        # ✅ Calcular ventas
        total_sales = self.transactions.filter(
            type='SALE'
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        # ✅ Calcular gastos
        total_expenses = self.transactions.filter(
            type='EXPENSE'
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        # ✅ Calcular retiros
        total_withdrawals = self.transactions.filter(
            type='WITHDRAWAL'
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        # ✅ Actualizar campos
        self.total_sales = total_sales
        self.total_expenses = total_expenses
        self.total_withdrawals = total_withdrawals
        self.expected_total = (
            self.initial_amount + 
            self.total_sales - 
            self.total_expenses - 
            self.total_withdrawals
        )
        
        # ✅ Guardar sin recursión
        super().save(update_fields=[
            'total_sales', 'total_expenses', 
            'total_withdrawals', 'expected_total'
        ])
        
        return self.expected_total

    def close(self, counted_total, breakdown=None, note=''):
        """Cerrar caja"""
        if self.status != 'OPEN':
            raise ValidationError("Solo se puede cerrar una caja abierta")
        
        from django.utils import timezone
        
        # ✅ Recalcular antes de cerrar
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
        """Generar número automáticamente si no existe"""
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
        
        # ✅ Si se está abriendo, asegurar que no haya otra caja abierta
        if self.status == 'OPEN' and self.pk is None:
            # Verificar si ya hay una caja abierta para este usuario
            existing_open = CashRegister.objects.filter(
                user=self.user,
                status='OPEN'
            ).exists()
            
            if existing_open:
                raise ValidationError(
                    f"El usuario {self.user.username} ya tiene una caja abierta. "
                    "Debe cerrarla antes de abrir una nueva."
                )
        
        super().save(*args, **kwargs)


class CashTransaction(models.Model):
    """Transacción de caja"""
    
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
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Creado"
    )

    class Meta:
        verbose_name = "Transacción de Caja"
        verbose_name_plural = "Transacciones de Caja"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.get_type_display()} - {self.amount} - {self.description}"