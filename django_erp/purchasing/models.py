# django_erp/purchasing/models.py
from django.db import models
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from simple_history.models import HistoricalRecords
from decimal import Decimal
from decimal import Decimal, ROUND_HALF_UP
from django_erp.configuration.models import Company, Currency, ExchangeRate
import uuid
import logging
logger = logging.getLogger(__name__)

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
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        verbose_name="Compañía/Sucursal",
        related_name='supplier'
    )
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
        ('SENT', 'Enviado al Proveedor'),
        ('CONFIRMED', 'Confirmado por Proveedor'),
        ('RECEIVED', 'Recibido'),
        ('CANCELLED', 'Cancelado'),
    ]

    sent_date = models.DateTimeField(
        null=True, 
        blank=True,
        verbose_name="Fecha de Envío"
    )
    confirmed_date = models.DateTimeField(
        null=True, 
        blank=True,
        verbose_name="Fecha de Confirmación"
    )
    received_date = models.DateTimeField(
        null=True, 
        blank=True,
        verbose_name="Fecha de Recepción"
    )
    
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

    invoice_ids = models.ManyToManyField(
        'purchasing.PurchaseInvoice',
        blank=True,
        verbose_name="Facturas"
    )
    invoiced = models.BooleanField(
        default=False,
        verbose_name="¿Facturado?"
    )
    invoice_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="Fecha de Facturación"
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
        related_name='purchaseorder'
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
        """Calcular totales usando el IVA de la empresa"""
        from decimal import Decimal, ROUND_HALF_UP
        from django_erp.configuration.models import Company
        
        # ✅ Solo calcular si ya tiene ID
        if not self.pk:
            return
        
        # ✅ Asegurar que subtotal sea Decimal
        subtotal = Decimal('0.00')
        for line in self.lines.all():
            subtotal += Decimal(str(line.subtotal))
        
        # ✅ Obtener IVA de la empresa
        company = Company.get_active()
        if company:
            tax_rate = Decimal(str(company.tax_rate))
        else:
            tax_rate = Decimal('16.00')
        
        tax = subtotal * (tax_rate / Decimal('100'))
        total = subtotal + tax
        
        # ✅ Redondear a 2 decimales
        self.subtotal = subtotal.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        self.tax = tax.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        self.total = total.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        
        return self.subtotal, self.tax, self.total

    def save(self, *args, **kwargs):
        """Guardar - Igual que invoicing"""
        # ✅ RED DE SEGURIDAD: si no viene compañía asignada (por ejemplo,
        # al crear una orden fuera del admin), usar la compañía activa.
        if not self.company_id:
            company = Company.get_active()
            if company:
                self.company = company

        # ✅ Si es nueva orden, establecer tasa de IVA desde la empresa
        if not self.pk:
            if not self.tax_rate or self.tax_rate == 0:
                company = Company.get_active()
                if company:
                    self.tax_rate = Decimal(str(company.tax_rate))
                else:
                    self.tax_rate = Decimal('16.00')
        
        # ✅ Guardar primero para tener ID
        super().save(*args, **kwargs)


        # ✅ Calcular totales SOLO si tiene líneas
        if self.pk and self.lines.exists():
            self.calculate_totals()
            # ✅ Guardar solo los campos de totales (evita recursión)
            super().save(update_fields=['subtotal', 'tax', 'total'])


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
        'inventory.Product',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Producto",
        related_name='purchase_line_products'
    )
    
    # Ubicación sugerida para el producto al recibirlo
    location = models.ForeignKey(
        'inventory.Location',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Ubicación",
        help_text="Ubicación sugerida para el producto en el almacén",
        related_name='purchase_line_locations'
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

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        verbose_name="Compañía/Sucursal",
        related_name='purchaseline'
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
        # ✅ RED DE SEGURIDAD: heredar la compañía de la orden padre si no
        # viene asignada explícitamente (por admin, shell, API, etc.)
        if not self.company_id and self.order_id:
            self.company_id = self.order.company_id

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


class PurchasePayment(models.Model):
    """Pago a proveedor (compras) - Usa cuentas de la empresa"""
    
    # ✅ Relación con la orden de compra
    purchase_order = models.ForeignKey(
        'purchasing.PurchaseOrder',
        on_delete=models.CASCADE,
        related_name='payments',
        verbose_name="Orden de Compra",
        null=True,
        blank=True,
    )

    purchase_invoice = models.ForeignKey(
        'purchasing.PurchaseInvoice',
        on_delete=models.CASCADE,
        related_name='payments',
        verbose_name="Factura de Compra",
        null=True,
        blank=True,
        help_text="Factura a la que pertenece este pago."
    )
    
    # ✅ Proveedor (para saber a quién se paga)
    supplier = models.ForeignKey(
        'purchasing.Supplier',
        on_delete=models.PROTECT,
        null=True,      
        blank=True,     
        related_name='payments',
        verbose_name="Proveedor"
    )    
    # ✅ Método de pago (reutilizado)
    method = models.ForeignKey(
        'configuration.PaymentMethod',
        on_delete=models.PROTECT,
        verbose_name="Método de Pago"
    )
    
    # ✅ Cuenta bancaria de la EMPRESA (desde donde se paga)
    company_bank_account = models.ForeignKey(
        'configuration.CompanyBankAccount',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        verbose_name="Cuenta de la empresa",
        help_text="Cuenta desde la cual se realiza el pago"
    )

    # ✅ Moneda en la que se paga
    currency = models.ForeignKey(
        'configuration.Currency',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        verbose_name="Moneda"
    )

    # ✅ Monto pagado
    amount = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        verbose_name="Monto"
    )

    # ✅ Monto convertido a USD (automático)
    amount_usd = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        editable=False,
        default=0,
        verbose_name="Monto en USD"
    )

    # ✅ Referencia (número de transferencia, cheque, etc.)
    reference = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Referencia"
    )
    
    # ✅ NUEVO: Banco del proveedor (solo texto, NO es FK)
    supplier_bank = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="Banco del proveedor",
        help_text="Banco al cual se realizó el pago"
    )
    
    # ✅ Fecha esperada de pago (para crédito)
    expected_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="Fecha esperada"
    )
    
    payment_date = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Pago")
    
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
        related_name='purchasepayment'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    history = HistoricalRecords()
    
    class Meta:
        verbose_name = "Pago de Compra"
        verbose_name_plural = "Pagos de Compras"
        ordering = ['-payment_date']

    def __str__(self):
        """Representación del pago"""
        # ✅ Si tiene orden de compra
        if self.purchase_order:
            return f"{self.purchase_order.number} - {self.method.name} - {self.amount}"
        # ✅ Si tiene factura
        elif self.purchase_invoice:
            return f"{self.purchase_invoice.number} - {self.method.name} - {self.amount}"
        # ✅ Si no tiene referencia (caso extremo)
        else:
            return f"Pago #{self.id} - {self.method.name} - {self.amount}"

    def clean(self):
        """✅ Validar que si el método requiere cuenta, se seleccione una"""
        if self.method and self.method.requires_company_bank and not self.company_bank_account:
            raise ValidationError({
                'company_bank_account': f'El método de pago "{self.method.name}" requiere una cuenta bancaria de la empresa.'
            })

    def save(self, *args, **kwargs):
        from django_erp.configuration.models import ExchangeRate, Currency
        from decimal import Decimal, ROUND_HALF_UP

        # ✅ RED DE SEGURIDAD: heredar la compañía de la orden de compra
        # padre si no viene asignada explícitamente.
        if not self.company_id:
            # Prioridad 1: Desde la factura
            if self.purchase_invoice and self.purchase_invoice.company:
                self.company = self.purchase_invoice.company
                logger.info(f"   ✅ Compañía asignada desde factura al pago: {self.company.code}")
            # Prioridad 2: Desde la orden de compra
            elif self.purchase_order and self.purchase_order.company:
                self.company = self.purchase_order.company
                logger.info(f"   ✅ Compañía asignada desde orden al pago: {self.company.code}")
            # Prioridad 3: Compañía activa
            else:
                from django_erp.configuration.models import Company
                company = Company.get_active()
                if company:
                    self.company = company
                    logger.info(f"   ✅ Compañía activa asignada al pago: {company.code}")

        self.clean()
        
        # ✅ Establecer moneda por defecto
        if not self.currency_id and self.method_id:
            if self.method.default_currency:
                self.currency = self.method.default_currency
        
        # ✅ Si la moneda es USD, el monto en USD es el mismo
        if self.currency and self.currency.code == 'USD':
            self.amount_usd = self.amount
        else:
            # ✅ Obtener la moneda base (USD)
            try:
                usd = Currency.objects.get(code='USD')
                # ✅ Si la moneda del pago es la base, no hay conversión
                if self.currency and self.currency == usd:
                    self.amount_usd = self.amount
                else:
                    # ✅ Convertir a USD
                    rate = ExchangeRate.get_today_rate(self.currency.code, 'USD')
                    if rate and rate > 0:
                        self.amount_usd = (self.amount / Decimal(str(rate))).quantize(
                            Decimal('0.01'), rounding=ROUND_HALF_UP
                        )
                    else:
                        self.amount_usd = self.amount
            except Currency.DoesNotExist:
                self.amount_usd = self.amount
        
        super().save(*args, **kwargs)


class PurchaseInvoice(models.Model):
    """Factura de Compra - Similar a Invoice pero para compras"""
    
    # UUID y sincronización (igual que Invoice)
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
    
    created_at_local = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        verbose_name="Creado localmente"
    )
    
    device_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name="Dispositivo de creación"
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
    
    # Estados
    STATUS_CHOICES = [
        ('DRAFT', 'Borrador'),
        ('ISSUED', 'Emitida'),
        ('PAID', 'Pagada'),
        ('CANCELLED', 'Anulada'),
    ]
    
    # Número de factura
    number = models.CharField(max_length=50, unique=True, verbose_name="Número Interno")
    
    # Relación con la orden de compra
    purchase_order = models.ForeignKey(
        'purchasing.PurchaseOrder',
        on_delete=models.CASCADE,
        related_name='invoices',
        verbose_name="Orden de Compra",
        null=True,
        blank=True 
    )
    
    # Proveedor (desde la orden)
    supplier = models.ForeignKey(
        'purchasing.Supplier',
        on_delete=models.PROTECT,
        verbose_name="Proveedor"
    )
    
    # Datos del proveedor (copia)
    supplier_name = models.CharField(
        max_length=200,
        verbose_name="Nombre del Proveedor"
    )
    supplier_rif = models.CharField(
        max_length=20,
        verbose_name="RIF del Proveedor"
    )
    supplier_address = models.TextField(
        blank=True,
        verbose_name="Dirección del Proveedor"
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
        related_name='purchaseinvoice'
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Creado")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Actualizado")
    history = HistoricalRecords()

    class Meta:
        verbose_name = "Factura de Compra"
        verbose_name_plural = "Facturas de Compra"
        ordering = ['-date_issued', '-created_at']
        permissions = [
            ("can_view_purchaseinvoice", "Puede ver facturas de compra"),
            ("can_edit_purchaseinvoice", "Puede editar facturas de compra"),
            ("can_delete_purchaseinvoice", "Puede eliminar facturas de compra"),
            ("can_issue_purchaseinvoice", "Puede emitir facturas de compra"),
            ("can_pay_purchaseinvoice", "Puede pagar facturas de compra"),
            ("can_cancel_purchaseinvoice", "Puede anular facturas de compra"),
        ]

    def __str__(self):
        return f"{self.number} - {self.supplier_name}"

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
        # ✅ Asignar UUID si no existe
        if not self.uuid:
            self.uuid = uuid.uuid4()

        # ✅ RED DE SEGURIDAD: Asignar la compañía activa si no tiene una.
        if not self.company_id:
            from django_erp.configuration.models import Company
            company = Company.get_active()
            if company:
                self.company = company
            # Si aún no hay compañía, se lanzará un error de integridad más abajo.

        # ✅ Si la factura está asociada a una orden de compra, copiar datos del proveedor.
        if self.purchase_order and self.purchase_order.supplier:
            self.supplier = self.purchase_order.supplier
            self.supplier_name = self.purchase_order.supplier.name
            self.supplier_rif = self.purchase_order.supplier.tax_id
            self.supplier_address = self.purchase_order.supplier.address

        # ✅ Guardar la instancia para obtener un ID si es nuevo.
        super().save(*args, **kwargs)
        
        # ✅ Recalcular totales si es una factura existente con líneas.
        if self.pk and hasattr(self, 'lines') and self.lines.exists():
            self.calculate_totals()
            # Guardar solo los campos de totales para evitar recursión.
            super().save(update_fields=['subtotal', 'tax', 'total'])


class PurchaseInvoiceLine(models.Model):
    """Línea de Factura de Compra"""
    
    uuid = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
        db_index=True,
        verbose_name="ID Universal"
    )
    
    invoice = models.ForeignKey(
        PurchaseInvoice,
        on_delete=models.CASCADE,
        related_name='lines',
        verbose_name="Factura de Compra"
    )
    
    # Relación con la línea de compra original
    purchase_line = models.ForeignKey(
        'purchasing.PurchaseLine',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Línea de Compra Original"
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
        related_name='purchaseinvoiceline'
    )
    history = HistoricalRecords()

    class Meta:
        verbose_name = "Línea de Factura de Compra"
        verbose_name_plural = "Líneas de Factura de Compra"

    def __str__(self):
        return f"{self.invoice.number} - {self.product_name or self.product_code or 'Sin producto'}"

    def save(self, *args, **kwargs):
        # ✅ Asignar UUID si no existe
        if not self.uuid:
            self.uuid = uuid.uuid4()
        
        # ✅ RED DE SEGURIDAD: Asignar compañía si no tiene
        if not self.company_id:
            # Primero intentar desde la factura
            if self.invoice and self.invoice.company:
                self.company = self.invoice.company
            else:
                # Fallback a compañía activa
                from django_erp.configuration.models import Company
                company = Company.get_active()
                if company:
                    self.company = company
        
        # ✅ Si la línea viene de una línea de compra, copiar datos
        if self.purchase_line:
            if self.purchase_line.product:
                self.product = self.purchase_line.product
                self.product_code = self.purchase_line.product.code
                self.product_name = self.purchase_line.product.name
            else:
                self.product_name = self.purchase_line.product_name
                self.product_code = self.purchase_line.product_code
            self.quantity = self.purchase_line.quantity
            self.unit_price = self.purchase_line.unit_price
            self.description = self.purchase_line.description or self.product_name
        
        # ✅ Calcular subtotal
        self.subtotal = self.quantity * self.unit_price
        
        super().save(*args, **kwargs)