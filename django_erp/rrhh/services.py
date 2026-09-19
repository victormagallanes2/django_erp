# rrhh/services.py
from decimal import Decimal, ROUND_HALF_UP
from django.core.exceptions import ValidationError
from .models import Employee, Commission
import logging

logger = logging.getLogger(__name__)


class CommissionService:
    """Servicio para el cálculo y registro de comisiones"""

    @staticmethod
    def _calculate_commission_base(invoice):
        """
        Calcular la base sobre la que se aplica la comisión, según configuración
        de la compañía.

        - Si commission_by_service_only = False → subtotal completo de la factura.
        - Si commission_by_service_only = True → suma de subtotales de líneas
          consideradas "servicio". Se considera servicio a:
            * Líneas cuyo product.is_service = True
            * Líneas sin product pero con product_name (servicios manuales)
        """
        company = invoice.company
        if not company:
            return Decimal('0.00')

        if not company.commission_by_service_only:
            # ✅ Comisión sobre el total de la factura
            return invoice.subtotal or Decimal('0.00')

        # ✅ Comisión solo sobre servicios
        total_services = Decimal('0.00')
        for line in invoice.lines.all():
            subtotal = Decimal(str(line.subtotal or 0))

            # Caso 1: producto marcado como servicio
            if line.product and line.product.is_service:
                total_services += subtotal
                continue

            # Caso 2: línea sin producto pero con nombre → servicio manual
            if not line.product and line.product_name:
                total_services += subtotal
                continue

            # Caso 3: cualquier otra línea → no comisionable
            # (productos físicos con product.is_service = False)

        return total_services

    @staticmethod
    def create_commission_for_invoice(invoice):
        """
        Crear una comisión para la factura pagada.

        Reglas:
        - Solo si la compañía tiene commission_enabled = True
        - Solo si la factura tiene salesperson asignado
        - Solo si el empleado tiene commission_rate > 0
        - Solo si la base comisionable > 0
        - No duplica comisiones para la misma factura/empleado
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

        # ✅ 2. ¿Hay vendedor asignado?
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

        # ✅ 5. Calcular la base comisionable
        base_amount = CommissionService._calculate_commission_base(invoice)
        modo = 'servicios' if company.commission_by_service_only else 'factura completa'
        logger.info(f"   - Modo: {modo}")
        logger.info(f"   - Base comisionable: {base_amount}")

        if base_amount <= 0:
            logger.info(f"   ℹ️ Factura {invoice.number} sin base comisionable → no genera comisión")
            return None

        rate = employee.commission_rate
        amount = (base_amount * rate / Decimal('100')).quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP
        )

        commission = Commission.objects.create(
            employee=employee,
            sale_invoice=invoice,
            company=invoice.company,
            base_amount=base_amount,
            rate=rate,
            amount=amount,
            status='PENDING',
        )

        logger.info(
            f"   ✅ Comisión creada: {employee} → ${amount} "
            f"({rate}% de ${base_amount}, modo={modo})"
        )
        logger.info("=" * 80)
        return commission