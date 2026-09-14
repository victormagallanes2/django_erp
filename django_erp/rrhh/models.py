# rrhh/models.py
from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from decimal import Decimal, ROUND_HALF_UP


class Employee(models.Model):
    """Modelo básico de empleado relacionado con User"""
    
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='employee',
        verbose_name=_("Usuario")
    )
    
    employee_code = models.CharField(
        max_length=20,
        unique=True,
        verbose_name=_("Código de empleado")
    )
    
    commission_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('5.00'),
        verbose_name=_("Comisión (%)"),
        help_text=_("Porcentaje de comisión sobre el subtotal de las ventas")
    )

    hire_date = models.DateField(
        verbose_name=_("Fecha de contratación"),
        null=True,
        blank=True
    )
    
    position = models.CharField(
        max_length=100,
        verbose_name=_("Cargo"),
        blank=True
    )

    pin = models.CharField(
        max_length=6,
        blank=True,
        null=True,
        unique=True,
        verbose_name="PIN de acceso",
        help_text=(
            "PIN numérico de 4 a 6 dígitos para identificar al empleado "
            "al momento de facturar. Debe ser único entre empleados activos."
        )
    )
    
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = _("Empleado")
        verbose_name_plural = _("Empleados")
        ordering = ['user__first_name', 'user__last_name']
    
    def __str__(self):
        return f"{self.user.get_full_name()} ({self.employee_code})"
    
    def save(self, *args, **kwargs):
        # Auto-generar código de empleado si no se proporciona
        if not self.employee_code:
            # Ejemplo: EMP-0001, EMP-0002, etc.
            last_employee = Employee.objects.order_by('-id').first()
            if last_employee:
                last_code = int(last_employee.employee_code.split('-')[1])
                self.employee_code = f"EMP-{str(last_code + 1).zfill(4)}"
            else:
                self.employee_code = "EMP-0001"
        super().save(*args, **kwargs)

    @property
    def is_active(self):
        """El empleado está activo si su usuario lo está"""
        return self.user.is_employee and self.user.is_active

    def clean(self):
        super().clean()
        if self.pin:
            # Solo dígitos
            if not self.pin.isdigit():
                raise ValidationError("El PIN debe contener solo números.")
            if len(self.pin) < 4 or len(self.pin) > 6:
                raise ValidationError("El PIN debe tener entre 4 y 6 dígitos.")
            # ✅ Unicidad entre empleados activos (por si el unique=True no basta con nulls)
            if self.pk:
                qs = Employee.objects.filter(pin=self.pin).exclude(pk=self.pk)
            else:
                qs = Employee.objects.filter(pin=self.pin)
            if qs.exists():
                raise ValidationError(f"El PIN '{self.pin}' ya está asignado a otro empleado.")


class Commission(models.Model):
    """Comisión generada por una venta de un empleado"""
    
    STATUS_CHOICES = [
        ('PENDING', _('Pendiente')),
        ('PAID', _('Pagada')),
        ('CANCELLED', _('Cancelada')),
    ]
    
    employee = models.ForeignKey(
        Employee,
        on_delete=models.PROTECT,
        related_name='commissions',
        verbose_name=_("Empleado")
    )
    
    sale_invoice = models.ForeignKey(
        'sales.SaleInvoice',
        on_delete=models.CASCADE,
        related_name='commissions',
        verbose_name=_("Factura")
    )
    
    # ✅ Snapshot del cálculo (por si cambia el % después)
    base_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name=_("Base (subtotal sin IVA)")
    )
    
    rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        verbose_name=_("Porcentaje aplicado (%)")
    )
    
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name=_("Monto comisión")
    )
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='PENDING',
        verbose_name=_("Estado")
    )
    
    paid_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Fecha de pago")
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = _("Comisión")
        verbose_name_plural = _("Comisiones")
        ordering = ['-created_at']
        # ✅ Evitar duplicados por factura+empleado
        constraints = [
            models.UniqueConstraint(
                fields=['employee', 'sale_invoice'],
                name='unique_commission_per_invoice_employee'
            )
        ]
        permissions = [
            ("can_view_commission", "Puede ver comisiones"),
            ("can_pay_commission", "Puede marcar comisiones como pagadas"),
        ]
    
    def __str__(self):
        return f"{self.employee} - {self.sale_invoice.number} - ${self.amount}"