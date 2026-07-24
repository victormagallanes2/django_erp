# invoicing/services.py
from django.db import transaction
from django.core.exceptions import ValidationError
from decimal import Decimal, ROUND_HALF_UP
from .models import Invoice, InvoiceLine
from django_erp.configuration.models import Company, ExchangeRate
from django.apps import apps
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class InvoiceService:
    
    @staticmethod
    @transaction.atomic
    def create_invoice_from_sale_order(sale_order_id, user=None):
        """
        Crear factura desde orden de venta con pagos en múltiples monedas
        """
        
        # ✅ Verificar que Sales está instalado
        if not apps.is_installed('django_erp.sales'):
            raise ValidationError("El módulo Sales no está instalado")
        
        from django_erp.sales.models import SaleOrder
        sale_order = SaleOrder.objects.get(id=sale_order_id)
        
        # ✅ Validaciones
        if sale_order.status == 'DRAFT':
            raise ValidationError("No se puede facturar una orden en borrador")
        
        if hasattr(sale_order, 'invoice') and sale_order.invoice:
            raise ValidationError("Esta orden ya tiene una factura")
        
        company = Company.get_active()
        if not company:
            raise ValidationError("No hay una empresa configurada")
        
        # ✅ Generar número de factura
        last_invoice = Invoice.objects.order_by('-id').first()
        if last_invoice and last_invoice.number:
            try:
                last_num = int(last_invoice.number.split('-')[-1])
                next_num = last_num + 1
            except (ValueError, IndexError):
                next_num = 1
        else:
            next_num = 1
        
        number = f"{company.invoice_prefix}-{datetime.now().strftime('%Y%m')}-{next_num:04d}"
        
        # ============================================================
        # ✅ PROCESAR PAGOS
        # ============================================================
        
        payments = sale_order.payments.all()
        payment_summary = {}
        total_paid_usd = Decimal('0.00')
        change_by_currency = {}
        
        # ✅ Agrupar pagos por moneda
        payments_by_currency = {}
        for payment in payments:
            currency_code = payment.currency.code
            if currency_code not in payments_by_currency:
                payments_by_currency[currency_code] = []
            payments_by_currency[currency_code].append(payment)
            # ✅ Asegurar que amount_usd sea Decimal
            amount_usd = Decimal(str(payment.amount_usd))
            total_paid_usd += amount_usd
        
        # ✅ Redondear total_paid_usd a 2 decimales
        total_paid_usd = total_paid_usd.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        
        # ✅ Calcular total de la factura (REDONDEADO A 2 DECIMALES)
        subtotal = Decimal('0.00')
        for line in sale_order.lines.all():
            subtotal += Decimal(str(line.subtotal))
        
        # ✅ Redondear subtotal a 2 decimales
        subtotal = subtotal.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        
        tax_rate = Decimal(str(company.tax_rate))
        tax = (subtotal * (tax_rate / Decimal('100'))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        total = (subtotal + tax).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        
        # ✅ Calcular vuelto por moneda
        for currency_code, pymts in payments_by_currency.items():
            total_in_currency = sum(p.amount for p in pymts)
            rate = ExchangeRate.get_today_rate('USD', currency_code)
            if rate:
                total_usd_in_currency = total * rate
            else:
                total_usd_in_currency = total
            
            if total_in_currency > total_usd_in_currency:
                change = (total_in_currency - total_usd_in_currency).quantize(
                    Decimal('0.01'), rounding=ROUND_HALF_UP
                )
                change_by_currency[currency_code] = float(change)
        
        # ✅ Crear resumen de pagos (convertir Decimal a float con 2 decimales)
        for payment in payments:
            currency_code = payment.currency.code
            key = f"{currency_code}:{payment.method.code}"
            if key not in payment_summary:
                payment_summary[key] = {
                    'method': payment.method.code,
                    'method_name': payment.method.name,
                    'currency': currency_code,
                    'amount': float(payment.amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)),
                    'amount_usd': float(payment.amount_usd.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))
                }
            else:
                payment_summary[key]['amount'] += float(payment.amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))
                payment_summary[key]['amount_usd'] += float(payment.amount_usd.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))
        
        # ============================================================
        # ✅ CREAR FACTURA
        # ============================================================
        
        invoice = Invoice.objects.create(
            number=number,
            company=company,
            issuer_rif=company.rif,
            issuer_name=company.name,
            issuer_address=company.address,
            customer=sale_order.customer,
            customer_name=sale_order.customer.name,
            customer_rif=sale_order.customer.tax_id,
            customer_address=sale_order.customer.address,
            sale_order_number=sale_order.number,
            status='DRAFT',
            tax_rate=company.tax_rate,
            user=user or sale_order.user,
            sync_status='SYNCED',
            payment_summary=payment_summary,
            paid_amount=float(total_paid_usd),
            change_amount=float((total_paid_usd - total).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)),
            change_summary=change_by_currency,
        )
        
        # ============================================================
        # ✅ COPIAR LÍNEAS
        # ============================================================
        
        for line in sale_order.lines.all():
            # ✅ Calcular subtotal de la línea con 2 decimales
            line_subtotal = (Decimal(str(line.quantity)) * Decimal(str(line.unit_price))).quantize(
                Decimal('0.01'), rounding=ROUND_HALF_UP
            )
            
            InvoiceLine.objects.create(
                invoice=invoice,
                product_code=line.product.code if line.product else '',
                product_name=line.product.name if line.product else line.product_name,
                description=line.description or line.product_name,
                quantity=line.quantity,
                unit_price=Decimal(str(line.unit_price)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
                subtotal=line_subtotal
            )
        
        # ============================================================
        # ✅ CALCULAR TOTALES Y GUARDAR
        # ============================================================
        
        invoice.calculate_totals()
        invoice.save()
        
        logger.info(f'✅ Factura {invoice.number} creada desde orden {sale_order.number}')
        logger.info(f'   Pagos: {len(payment_summary)}')
        logger.info(f'   Total pagado: ${float(total_paid_usd):.2f}')
        logger.info(f'   Cambio: ${float(total_paid_usd - total):.2f}')
        
        return invoice
    
    @staticmethod
    @transaction.atomic
    def issue_invoice(invoice, user=None):
        """Emitir una factura"""
        if not invoice.lines.exists():
            raise ValidationError("No se puede emitir una factura sin líneas")
        invoice.status = 'ISSUED'
        invoice.save()
        return invoice
    
    @staticmethod
    @transaction.atomic
    def pay_invoice(invoice, user=None):
        """Registrar pago de una factura"""
        invoice.status = 'PAID'
        invoice.save()
        return invoice
    
    @staticmethod
    @transaction.atomic
    def cancel_invoice(invoice, user=None):
        """Anular una factura"""
        invoice.status = 'CANCELLED'
        invoice.save()
        return invoice