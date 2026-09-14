# rrhh/services.py
from decimal import Decimal, ROUND_HALF_UP
from django.core.exceptions import ValidationError
from .models import Employee, Commission
import logging

logger = logging.getLogger(__name__)


class CommissionService:
    """Servicio para el cálculo y registro de comisiones"""

    @staticmethod
    def create_commission_for_invoice(invoice):
        """
        Crear una comisión para la factura pagada.

        Reglas:
        - Solo si la compañía tiene commission_enabled = True
        - Solo si la factura tiene salesperson asignado
        - Solo si el empleado tiene commission_rate > 0
        - Solo si el subtotal > 0
        - No duplica comisiones para la misma factura/empleado

        Retorna la Commission creada, la existente, o None.
        """
        logger.info("=" * 80)
        logger.info(f"🔍 [create_commission_for_invoice] Factura {invoice.number}")

        # ✅ 1. ¿La compañía tiene comisiones habilitadas?
        company = invoice.company
        if not company:
            logger.info("   ❌ Factura sin compañía → no genera comisión")
            return None

        if not company.commission_enabled:
            logger.info(f"   ℹ️ Compañía {company.code} no tiene comisiones habilitadas")
            return None


        if not invoice.salesperson_id:
            logger.info(f"   ℹ️ Factura {invoice.number} sin vendedor asignado")
            return None

        employee = invoice.salesperson
        logger.info(f"   - Vendedor: {employee}")

        # ✅ 3. ¿El empleado tiene tasa de comisión?
        if not employee.commission_rate or employee.commission_rate <= 0:
            logger.info(f"   ℹ️ Empleado {employee} sin comisión configurada")
            return None

        # ✅ 4. Evitar duplicados
        existing = Commission.objects.filter(
            employee=employee,
            sale_invoice=invoice
        ).first()
        if existing:
            logger.info(f"   ℹ️ Comisión ya existe para factura {invoice.number}")
            return existing

        # ✅ 5. Calcular sobre el subtotal (sin IVA)
        base_amount = invoice.subtotal or Decimal('0.00')
        if base_amount <= 0:
            logger.info(f"   ℹ️ Factura {invoice.number} sin subtotal → no genera comisión")
            return None

        rate = employee.commission_rate
        amount = (base_amount * rate / Decimal('100')).quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP
        )

        commission = Commission.objects.create(
            employee=employee,
            sale_invoice=invoice,
            base_amount=base_amount,
            rate=rate,
            amount=amount,
            status='PENDING',
        )

        logger.info(
            f"   ✅ Comisión creada: {employee} → ${amount} "
            f"({rate}% de ${base_amount})"
        )
        logger.info("=" * 80)
        return commission