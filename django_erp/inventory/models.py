# inventory/models.py
from django.db import models
from django.contrib.auth import get_user_model
from simple_history.models import HistoricalRecords
import uuid

# ✅ NO importamos nada de warehouse
# ✅ Usamos referencias dinámicas

User = get_user_model()


class Inventory(models.Model):
    """Inventario contable por producto y ubicación"""
    
    # ✅ Referencias dinámicas
    product = models.ForeignKey(
        'warehouse.Product',  # ← Texto, no importación
        on_delete=models.CASCADE,
        related_name='inventories',
        verbose_name="Producto"
    )
    location = models.ForeignKey(
        'warehouse.Location',  # ← Texto, no importación
        on_delete=models.CASCADE,
        related_name='inventories',
        verbose_name="Ubicación"
    )
    
    quantity = models.IntegerField(default=0, verbose_name="Cantidad")
    average_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Costo promedio")
    total_value = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Valor total")
    
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Actualizado")
    history = HistoricalRecords()
    
    class Meta:
        verbose_name = "Inventario"
        verbose_name_plural = "Inventarios"
        unique_together = [['product', 'location']]
        permissions = [
            ("can_view_inventory", "Puede ver inventarios"),
            ("can_edit_inventory", "Puede editar inventarios"),
        ]
    
    def __str__(self):
        return f"{self.product.name} - {self.location.code}: {self.quantity}"


class ValuationMethod(models.Model):
    """Método de valoración de inventario"""
    
    METHOD_CHOICES = [
        ('FIFO', 'FIFO (First In First Out)'),
        ('LIFO', 'LIFO (Last In First Out)'),
        ('AVERAGE', 'Costo Promedio'),
        ('STANDARD', 'Costo Estándar'),
    ]
    
    # ✅ Referencia dinámica
    product = models.OneToOneField(
        'warehouse.Product',  # ← Texto, no importación
        on_delete=models.CASCADE,
        related_name='valuation_method',
        verbose_name="Producto"
    )
    method = models.CharField(max_length=10, choices=METHOD_CHOICES, default='AVERAGE', verbose_name="Método")
    standard_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Costo estándar")
    history = HistoricalRecords()
    
    class Meta:
        verbose_name = "Método de Valoración"
        verbose_name_plural = "Métodos de Valoración"
        permissions = [
            ("can_view_valuationmethod", "Puede ver métodos de valoración"),
            ("can_edit_valuationmethod", "Puede editar métodos de valoración"),
        ]
    
    def __str__(self):
        return f"{self.product.name} - {self.get_method_display()}"


class PhysicalCount(models.Model):

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
        db_index=True,
        verbose_name="Estado de sincronización"
    )
    
    # ✅ NUEVO: Device ID
    device_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name="Dispositivo de creación"
    )

    """Conteo físico de inventario"""
    
    STATUS_CHOICES = [
        ('DRAFT', 'Borrador'),
        ('CONFIRMED', 'Confirmado'),
        ('CANCELLED', 'Cancelado'),
    ]
    
    # ✅ Referencias dinámicas
    product = models.ForeignKey(
        'warehouse.Product',  # ← Texto, no importación
        on_delete=models.CASCADE,
        related_name='physical_counts',
        verbose_name="Producto"
    )
    location = models.ForeignKey(
        'warehouse.Location',  # ← Texto, no importación
        on_delete=models.CASCADE,
        related_name='physical_counts',
        verbose_name="Ubicación"
    )
    
    count_date = models.DateField(auto_now_add=True, verbose_name="Fecha de conteo")
    counted_quantity = models.IntegerField(verbose_name="Cantidad contada")
    system_quantity = models.IntegerField(verbose_name="Cantidad en sistema")
    difference = models.IntegerField(editable=False, verbose_name="Diferencia")
    
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='DRAFT', verbose_name="Estado")
    note = models.TextField(blank=True, verbose_name="Nota")
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name="Usuario")
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Creado")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Actualizado")
    history = HistoricalRecords()
    
    class Meta:
        verbose_name = "Conteo Físico"
        verbose_name_plural = "Conteos Físicos"
        ordering = ['-count_date']
        permissions = [
            ("can_view_physicalcount", "Puede ver conteos físicos"),
            ("can_create_physicalcount", "Puede crear conteos físicos"),
            ("can_confirm_physicalcount", "Puede confirmar conteos físicos"),
        ]

        indexes = [
            models.Index(fields=['uuid']),
            models.Index(fields=['sync_status']),
        ]
    
    def __str__(self):
        return f"{self.product.name} - {self.count_date}"
    
    def save(self, *args, **kwargs):
        if not self.uuid:
            self.uuid = uuid.uuid4()
        self.difference = self.counted_quantity - self.system_quantity
        super().save(*args, **kwargs)
