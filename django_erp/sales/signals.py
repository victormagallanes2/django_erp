# sales/signals.py - CON SEÑALES PARA CREAR NOTAS DE ENTREGA Y SEÑAL order_confirmed
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver, Signal
from django.core.exceptions import ValidationError
from .models import SaleOrder, SaleInvoice
from .services import SaleService
import logging

logger = logging.getLogger(__name__)

# ✅ SEÑAL PARA CUANDO UNA ORDEN ES CONFIRMADA
order_confirmed = Signal()

invoice_paid = Signal()


@receiver(pre_save, sender=SaleOrder)
def check_status_transition(sender, instance, **kwargs):
    """
    ✅ Validar transiciones de estado antes de guardar.
    """
    if not instance.pk:
        return
    
    try:
        old = SaleOrder.objects.get(pk=instance.pk)
        if old.status != instance.status:
            if not SaleService.can_transition(instance, instance.status, old.status):
                raise ValidationError(
                    f"No se puede cambiar de '{old.get_status_display()}' a "
                    f"'{instance.get_status_display()}'"
                )
    except SaleOrder.DoesNotExist:
        pass


@receiver(post_save, sender=SaleOrder)
def create_delivery_note_on_confirm(sender, instance, created, **kwargs):
    """
    ✅ Cuando una venta se confirma, crear una Nota de Entrega en Borrador.
    """
    # Solo ejecutar si el estado cambió a CONFIRMED
    if instance.pk:
        try:
            old = SaleOrder.objects.get(pk=instance.pk)
            # Si el estado cambió a CONFIRMED y antes no lo estaba
            if old.status != 'CONFIRMED' and instance.status == 'CONFIRMED':
                logger.info("=" * 80)
                logger.info(f"🔴 [create_delivery_note_on_confirm] Orden {instance.number} confirmada")
                logger.info("   🔄 Creando nota de entrega...")
                
                # Llamar al servicio para crear la nota de entrega
                # Pero solo si no se ha creado ya (evitar duplicados)
                from django_erp.inventory.models import DeliveryNote
                existing = DeliveryNote.objects.filter(
                    customer=instance.customer,
                    customer_name=instance.customer.name,
                    notes__icontains=f"Venta {instance.number}",
                    company=instance.company,
                    status='DRAFT'
                ).first()
                
                if not existing:
                    SaleService.confirm_order(instance, instance.user)
                    logger.info(f"   ✅ Nota de entrega creada para orden {instance.number}")
                else:
                    logger.info(f"   ℹ️ Nota de entrega ya existe para orden {instance.number}")
                logger.info("=" * 80)
        except SaleOrder.DoesNotExist:
            pass


@receiver(post_save, sender=SaleInvoice)
def register_cash_on_invoice_paid(sender, instance, created, **kwargs):
    """
    ✅ Cuando una factura cambia a PAID, registrar en caja.
    """
    # Solo ejecutar si la factura está en estado PAID
    if instance.status == 'PAID':
        logger.info("=" * 80)
        logger.info(f"🔴 [register_cash_on_invoice_paid] Factura {instance.number} está PAGADA")
        
        # ✅ Asegurar que los totales están actualizados
        instance.refresh_from_db()
        
        # ✅ Verificar que el monto total sea mayor a 0
        if instance.total <= 0:
            logger.warning(f"   ⚠️ El total de la factura es {instance.total}, no se registra en caja")
            logger.info("=" * 80)
            return
        
        # Verificar que la factura tenga un usuario asociado
        user = instance.user
        if not user:
            logger.warning(f"   ⚠️ Factura {instance.number} sin usuario asignado")
            logger.info("=" * 80)
            return
        
        # Verificar que no exista ya una transacción para esta factura
        from .models import CashTransaction
        existing = CashTransaction.objects.filter(
            reference=instance.number,
            type='SALE'
        ).first()
        
        if existing:
            logger.info(f"   ℹ️ Transacción ya existe para factura {instance.number} con monto: {existing.amount}")
            logger.info("=" * 80)
            return
        
        # Registrar la transacción en caja
        from .helpers import get_open_register
        from django_erp.configuration.models import PaymentMethod, Currency
        
        try:
            register = get_open_register(user)
            logger.info(f"   ✅ Caja abierta: {register.number}")
            
            # ✅ Crear transacción con el total correcto
            transaction = CashTransaction.objects.create(
                register=register,
                type='SALE',
                amount=instance.total,  # ✅ Usar el total calculado
                description=f"Factura {instance.number} - {instance.customer_name}",
                reference=instance.number,
                user=user,
                company=instance.company,
            )
            logger.info(f"   ✅ Transacción creada con monto: {transaction.amount}")
            
            # Recalcular totales de la caja
            register.calculate_totals()
            logger.info(f"   ✅ Totales de caja recalculados")
            
            # Verificar si ya existe un pago para esta factura
            from .models import Payment
            existing_payment = Payment.objects.filter(
                sale_invoice=instance,
                status='COMPLETED'
            ).first()
            
            if not existing_payment:
                # Crear pago asociado
                default_method = PaymentMethod.objects.filter(
                    company=instance.company,
                    is_active=True
                ).first()
                
                if default_method:
                    try:
                        usd = Currency.objects.get(code='USD')
                    except Currency.DoesNotExist:
                        usd = None
                    
                    if usd:
                        Payment.objects.create(
                            sale_invoice=instance,
                            method=default_method,
                            currency=usd,
                            amount=instance.total,
                            amount_usd=instance.total,
                            reference=f"Pago factura {instance.number}",
                            status='COMPLETED',
                            user=user,
                            company=instance.company,
                        )
                        logger.info(f"   ✅ Pago creado para factura {instance.number}")
                else:
                    logger.warning(f"   ⚠️ No hay método de pago por defecto")
            else:
                logger.info(f"   ℹ️ Pago ya existe para factura {instance.number}")
            
            logger.info(f"   ✅ Factura {instance.number} registrada en caja por ${instance.total:.2f}")
            
        except ValidationError as e:
            logger.error(f"   ❌ Error al registrar en caja: {e}")
        except Exception as e:
            logger.error(f"   ❌ Error inesperado: {e}")
            import traceback
            logger.error(f"   Traceback: {traceback.format_exc()}")
        
        logger.info("=" * 80)