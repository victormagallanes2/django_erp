# invoicing/services.py
from django.db import transaction
from django.core.exceptions import ValidationError
from decimal import Decimal
from .models import Invoice, InvoiceLine
from django_erp.configuration.models import Company
from django.apps import apps


class InvoiceService:
    
    @staticmethod
    @transaction.atomic
    def create_invoice_from_sale_order(sale_order_id, user=None):
        """Crear factura desde orden de venta (solo si Sales existe)"""
        
        if not apps.is_installed('django_erp.sales'):
            raise ValidationError("El módulo Sales no está instalado")
        
        from django_erp.sales.models import SaleOrder
        sale_order = SaleOrder.objects.get(id=sale_order_id)
        
        if sale_order.status == 'DRAFT':
            raise ValidationError("No se puede facturar una orden en borrador")
        
        if hasattr(sale_order, 'invoice') and sale_order.invoice:
            raise ValidationError("Esta orden ya tiene una factura")
        
        company = Company.get_active()
        if not company:
            raise ValidationError("No hay una empresa configurada")
        
        from datetime import datetime
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
            user=user
        )
        
        # Copiar líneas
        for line in sale_order.lines.all():
            InvoiceLine.objects.create(
                invoice=invoice,
                product_code=line.product.code,
                product_name=line.product.name,
                description=line.product.name,
                quantity=line.quantity,
                unit_price=line.unit_price
            )
        
        invoice.calculate_totals()
        invoice.save()
        
        return invoice
    
    @staticmethod
    @transaction.atomic
    def issue_invoice(invoice, user=None):
        """Emitir una factura"""
        if not invoice.lines.exists():
            raise ValidationError("No se puede emitir una factura sin líneas")
        return invoice
    
    @staticmethod
    @transaction.atomic
    def pay_invoice(invoice, user=None):
        """Registrar pago de una factura"""
        return invoice
    
    @staticmethod
    @transaction.atomic
    def cancel_invoice(invoice, user=None):
        """Anular una factura"""
        return invoice