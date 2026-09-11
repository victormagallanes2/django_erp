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
        Se basa en el empleado del usuario que generó la factura.
        Retorna la Commission creada o None si no aplica.
        """
        # ✅ Validaciones básicas
        if not invoice.user_id:
            logger.info(f"   ℹ️ Factura {invoice.number} sin usuario, no genera comisión")
            return None
        
        # ✅ El usuario debe tener un Employee asociado
        employee = getattr(invoice.user, 'employee', None)
        if not employee:
            logger.info(f"   ℹ️ Usuario {invoice.user.username} no es empleado, no genera comisión")
            return None
        
        # ✅ El empleado debe tener comisión > 0
        if not employee.commission_rate or employee.commission_rate <= 0:
            logger.info(f"   ℹ️ Empleado {employee} sin comisión configurada")
            return None
        
        # ✅ Evitar duplicados
        existing = Commission.objects.filter(
            employee=employee,
            sale_invoice=invoice
        ).first()
        if existing:
            logger.info(f"   ℹ️ Comisión ya existe para factura {invoice.number}")
            return existing
        
        # ✅ Calcular sobre el SUBTOTAL (sin IVA)
        base_amount = invoice.subtotal or Decimal('0.00')
        if base_amount <= 0:
            logger.info(f"   ℹ️ Factura {invoice.number} sin subtotal, no genera comisión")
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
        
        logger.info(f"   ✅ Comisión creada: {employee} → ${amount} ({rate}% de ${base_amount})")
        return commission