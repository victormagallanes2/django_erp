# inventory/models.py
from django.db import models
from django.contrib.auth import get_user_model
from simple_history.models import HistoricalRecords
import uuid
from decimal import Decimal
from django_erp.configuration.models import Company

User = get_user_model()


# ============================================================
# MODELOS DE ALMACÉN (ANTIGUO WAREHOUSE)
# ============================================================

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
    
    # ✅ PRECIO DE VENTA (antes llamado 'price')
    sale_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name="Precio de Venta (USD)",
        help_text="Precio al que se vende al cliente"
    )
    
    # ✅ NUEVO: PRECIO DE COMPRA (referencia)
    purchase_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name="Precio de Compra (USD)",
        help_text="Precio de compra para referencia. El costo real se calcula desde los movimientos."
    )
    
    is_service = models.BooleanField(
        default=False,
        verbose_name="¿Es servicio?",
        help_text="Marcar si es un servicio (no requiere control de stock)"
    )
    
    weight = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="Peso (kg)")
    dimensions = models.CharField(max_length=100, blank=True, verbose_name="Dimensiones (LxAxA)")
    image = models.ImageField(upload_to='products/', blank=True, null=True, verbose_name="Imagen")
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        verbose_name="Compañía/Sucursal",
        related_name='products'
    )
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
        from django_erp.configuration.models import Currency, ExchangeRate
        
        base = Currency.get_base()
        if not base:
            return self.price
        
        if currency_code == base.code:
            return self.price
        
        rate = ExchangeRate.get_rate(base.code, currency_code)
        return self.price * rate
    
    def get_price_display(self, currency_code=None):
        """Obtener precio con formato de moneda"""
        from django_erp.configuration.models import Currency
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
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        verbose_name="Compañía/Sucursal",
        related_name='locations'
    )
    is_active = models.BooleanField(default=True, verbose_name="Activo")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Creado")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Actualizado")
    history = HistoricalRecords()

    class Meta:
        verbose_name = "Ubicación"
        verbose_name_plural = "Ubicaciones"
        ordering = ['code']
        unique_together = [['code', 'company']]

    def __str__(self):
        return f"{self.code} - {self.name}"


class Movement(models.Model):
    """Movimiento FÍSICO - Cambia ubicación de productos"""

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
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        verbose_name="Compañía/Sucursal",
        related_name='movements'
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Creado")
    history = HistoricalRecords()

    class Meta:
        verbose_name = "Movimiento"
        verbose_name_plural = "Movimientos"
        ordering = ['-created_at']

        indexes = [
            models.Index(fields=['uuid']),
            models.Index(fields=['sync_status']),
        ]

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
        if not self.uuid:
            self.uuid = uuid.uuid4()
        self.total = self.quantity * self.unit_price
        self.clean()
        super().save(*args, **kwargs)


# ============================================================
# MODELOS DE INVENTARIO CONTABLE
# ============================================================

class Inventory(models.Model):
    """Inventario contable por producto y ubicación"""
    
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='inventories',
        verbose_name="Producto"
    )
    location = models.ForeignKey(
        Location,
        on_delete=models.CASCADE,
        related_name='inventories',
        verbose_name="Ubicación"
    )
    
    quantity = models.IntegerField(default=0, verbose_name="Cantidad")
    total_value = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Valor total")
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        verbose_name="Compañía/Sucursal",
        related_name='inventory'
    )
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Actualizado")
    history = HistoricalRecords()
    
    class Meta:
        verbose_name = "Inventario"
        verbose_name_plural = "Inventarios"
        unique_together = [['product', 'location', 'company']]
        permissions = [
            ("can_view_inventory", "Puede ver inventarios"),
            ("can_edit_inventory", "Puede editar inventarios"),
        ]
    
    def __str__(self):
        return f"{self.product.name} - {self.location.code}: {self.quantity}"




class PhysicalCount(models.Model):
    """Ajuste de inventario - Versión simplificada (aplicación directa)"""
    
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='physical_counts',
        verbose_name="Producto"
    )
    location = models.ForeignKey(
        Location,
        on_delete=models.CASCADE,
        related_name='physical_counts',
        verbose_name="Ubicación"
    )
    
    available_quantity = models.IntegerField(
        default=0,
        verbose_name="Cantidad disponible",
        help_text="Cantidad actual en el sistema (solo lectura)"
    )
    adjustment_quantity = models.IntegerField(
        default=0,
        verbose_name="Cantidad a ajustar",
        help_text="Nueva cantidad que debe quedar en el sistema"
    )
    
    difference = models.IntegerField(
        editable=False,
        default=0,
        verbose_name="Diferencia",
        help_text="Ajuste = Cantidad ajustada - Cantidad disponible"
    )
    
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
        related_name='physicalcount'
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Creado")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Actualizado")
    history = HistoricalRecords()
    
    class Meta:
        verbose_name = "Ajuste de Inventario"
        verbose_name_plural = "Ajustes de Inventario"
        ordering = ['-created_at']
        permissions = [
            ("can_view_physicalcount", "Puede ver ajustes de inventario"),
            ("can_create_physicalcount", "Puede crear ajustes de inventario"),
        ]

    def __str__(self):
        return f"{self.product.name} - {self.location.code}: {self.available_quantity} → {self.adjustment_quantity}"
    
    def save(self, *args, **kwargs):
        # Calcular la diferencia automáticamente
        self.difference = self.adjustment_quantity - self.available_quantity
        
        # Guardar el ajuste
        is_new = self.pk is None
        super().save(*args, **kwargs)
        
        # Si es nuevo, aplicar el ajuste inmediatamente
        if is_new and self.difference != 0:
            self._apply_adjustment()
    
    def _apply_adjustment(self):
        """Aplicar el ajuste al inventario"""
        from .models import Inventory, Movement
        
        try:
            # Obtener o crear el registro de inventario
            inventory, created = Inventory.objects.get_or_create(
                product=self.product,
                location=self.location,
                company=self.company,
                defaults={
                    'quantity': 0,
                    'total_value': 0,
                }
            )
            
            # Actualizar la cantidad
            inventory.quantity = self.adjustment_quantity
            inventory.save()
            
            # Crear un movimiento de ajuste para auditoría (solo si hay cambio)
            if self.difference != 0:
                Movement.objects.create(
                    product=self.product,
                    type='ADJUSTMENT',
                    quantity=abs(self.difference),
                    unit_price=0,
                    location_from=self.location if self.difference < 0 else None,
                    location_to=self.location if self.difference > 0 else None,
                    source_type='MANUAL',
                    source_reference=f"AJUSTE-{self.id}",
                    note=f"Ajuste de inventario: {self.available_quantity} → {self.adjustment_quantity}. {self.note}",
                    user=self.user,
                    company=self.company,
                )
                
        except Exception as e:
            raise Exception(f"Error al aplicar ajuste: {str(e)}")


class DeliveryNote(models.Model):
    """Nota de Entrega - Salida de productos del inventario."""
    
    STATUS_CHOICES = [
        ('DRAFT', 'Borrador'),
        ('CONFIRMED', 'Confirmado'),
        ('CANCELLED', 'Cancelado'),
    ]
    
    number = models.CharField(max_length=50, unique=True, verbose_name="Número de Nota")
    date = models.DateField(auto_now_add=True, verbose_name="Fecha")
    
    # ✅ NUEVO: Fecha de confirmación
    confirmed_date = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Fecha de Confirmación"
    )
    
    customer = models.ForeignKey(
        'sales.Customer',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        verbose_name="Cliente",
        related_name='delivery_notes'
    )
    customer_name = models.CharField(max_length=200, blank=True, verbose_name="Nombre del Cliente")
    notes = models.TextField(blank=True, verbose_name="Notas adicionales")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT', verbose_name="Estado")
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name="Usuario que creó")
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        verbose_name="Compañía/Sucursal",
        related_name='delivery_notes'
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Creado")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Actualizado")
    history = HistoricalRecords()

    class Meta:
        verbose_name = "Nota de Entrega"
        verbose_name_plural = "Notas de Entrega"
        ordering = ['-date', '-created_at']
        permissions = [
            ("can_view_deliverynote", "Puede ver notas de entrega"),
            ("can_edit_deliverynote", "Puede editar notas de entrega"),
            ("can_delete_deliverynote", "Puede eliminar notas de entrega"),
            ("can_confirm_deliverynote", "Puede confirmar notas de entrega"),
            ("can_cancel_deliverynote", "Puede cancelar notas de entrega"),
        ]

    def __str__(self):
        return f"{self.number} - {self.customer_name or self.customer.name if self.customer else 'Sin cliente'}"

    def save(self, *args, **kwargs):
        if not self.number:
            from datetime import datetime
            last_note = DeliveryNote.objects.order_by('-id').first()
            if last_note and last_note.number:
                try:
                    last_num = int(last_note.number.split('-')[-1])
                    next_num = last_num + 1
                except (ValueError, IndexError):
                    next_num = 1
            else:
                next_num = 1
            self.number = f"ENTREGA-{datetime.now().strftime('%Y%m%d')}-{next_num:04d}"
        super().save(*args, **kwargs)


class DeliveryNoteLine(models.Model):
    """Línea de Nota de Entrega"""
    
    note = models.ForeignKey(
        DeliveryNote,
        on_delete=models.CASCADE,
        related_name='lines',
        verbose_name="Nota de Entrega"
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        verbose_name="Producto",
        related_name='delivery_lines'
    )
    location = models.ForeignKey(
        Location,
        on_delete=models.PROTECT,
        verbose_name="Ubicación de salida",
        related_name='delivery_lines'
    )
    quantity = models.PositiveIntegerField(verbose_name="Cantidad")
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name='delivery_note_lines'
    )
    history = HistoricalRecords()

    class Meta:
        verbose_name = "Línea de Nota de Entrega"
        verbose_name_plural = "Líneas de Notas de Entrega"

    def __str__(self):
        return f"{self.note.number} - {self.product.name} x {self.quantity}"


class ReceiptNote(models.Model):
    """Nota de Recibo - Entrada de productos al inventario."""
    
    STATUS_CHOICES = [
        ('DRAFT', 'Borrador'),
        ('CONFIRMED', 'Confirmado'),
        ('CANCELLED', 'Cancelado'),
    ]
    
    number = models.CharField(max_length=50, unique=True, verbose_name="Número de Nota")
    date = models.DateField(auto_now_add=True, verbose_name="Fecha")
    purchase_order = models.ForeignKey(
        'purchasing.PurchaseOrder',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='receipt_notes',
        verbose_name="Orden de Compra",
        help_text="Orden de compra que originó esta nota (si aplica)."
    )
    supplier = models.ForeignKey(
        'purchasing.Supplier',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        verbose_name="Proveedor",
        related_name='receipt_notes'
    )
    supplier_name = models.CharField(max_length=200, blank=True, verbose_name="Nombre del Proveedor")
    notes = models.TextField(blank=True, verbose_name="Notas adicionales")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT', verbose_name="Estado")
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name="Usuario que creó")
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        verbose_name="Compañía/Sucursal",
        related_name='receipt_notes'
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Creado")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Actualizado")
    history = HistoricalRecords()

    class Meta:
        verbose_name = "Nota de Recibo"
        verbose_name_plural = "Notas de Recibo"
        ordering = ['-date', '-created_at']
        permissions = [
            ("can_view_receiptnote", "Puede ver notas de recibo"),
            ("can_edit_receiptnote", "Puede editar notas de recibo"),
            ("can_delete_receiptnote", "Puede eliminar notas de recibo"),
            ("can_confirm_receiptnote", "Puede confirmar notas de recibo"),
            ("can_cancel_receiptnote", "Puede cancelar notas de recibo"),
        ]

    def __str__(self):
        return f"{self.number} - {self.supplier_name or self.supplier.name if self.supplier else 'Sin proveedor'}"

    def save(self, *args, **kwargs):
        if not self.number:
            from datetime import datetime
            last_note = ReceiptNote.objects.order_by('-id').first()
            if last_note and last_note.number:
                try:
                    last_num = int(last_note.number.split('-')[-1])
                    next_num = last_num + 1
                except (ValueError, IndexError):
                    next_num = 1
            else:
                next_num = 1
            self.number = f"RECIBO-{datetime.now().strftime('%Y%m%d')}-{next_num:04d}"
        super().save(*args, **kwargs)


class ReceiptNoteLine(models.Model):
    """Línea de Nota de Recibo"""
    
    note = models.ForeignKey(
        ReceiptNote,
        on_delete=models.CASCADE,
        related_name='lines',
        verbose_name="Nota de Recibo"
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        verbose_name="Producto",
        related_name='receipt_lines'
    )
    location = models.ForeignKey(
        Location,
        on_delete=models.PROTECT,
        verbose_name="Ubicación de entrada",
        related_name='receipt_lines'
    )
    quantity = models.PositiveIntegerField(verbose_name="Cantidad")
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name='receipt_note_lines'
    )
    history = HistoricalRecords()

    class Meta:
        verbose_name = "Línea de Nota de Recibo"
        verbose_name_plural = "Líneas de Notas de Recibo"

    def __str__(self):
        return f"{self.note.number} - {self.product.name} x {self.quantity}"


