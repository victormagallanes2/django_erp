# invoicing/services.py
from django.db import transaction
from django.core.exceptions import ValidationError
from decimal import Decimal
from .models import Invoice, InvoiceLine
from django_erp.sales.models import SaleOrder
from django_erp.configuration.models import Company
from django_erp.warehouse.services import WarehouseService


class InvoiceService:
    """Servicios de facturación"""
    
    @staticmethod
    @transaction.atomic
    def create_invoice_from_sale_order(sale_order_id, user=None):
        """
        Crear una factura a partir de una orden de venta
        """
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
            sale_order=sale_order,
            number=number,
            company=company,
            issuer_rif=company.rif,
            issuer_name=company.name,
            issuer_address=company.address,
            customer=sale_order.customer,
            customer_rif=sale_order.customer.tax_id,
            customer_address=sale_order.customer.address,
            status='DRAFT',
            tax_rate=company.tax_rate,
            user=user
        )
        
        for line in sale_order.lines.all():
            InvoiceLine.objects.create(
                invoice=invoice,
                product=line.product,
                description=line.product.name,
                quantity=line.quantity,
                unit_price=line.unit_price
            )
        
        invoice.calculate_totals()
        invoice.save()
        
        if company.control_number_required:
            InvoiceService.request_control_number(invoice)
        
        return invoice
    
    @staticmethod
    def request_control_number(invoice):
        """Solicitar número de control (simulado)"""
        import datetime
        control_number = f"CTRL-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}-{invoice.id:04d}"
        invoice.control_number = control_number
        invoice.save()
        return control_number
    
    @staticmethod
    @transaction.atomic
    def issue_invoice(invoice, user=None):
        """
        Emitir una factura
        """
        # Solo verificar que tenga líneas
        if not invoice.lines.exists():
            raise ValidationError("No se puede emitir una factura sin líneas")
        return invoice
    
    @staticmethod
    @transaction.atomic
    def pay_invoice(invoice, user=None):
        """
        Registrar pago de una factura
        """
        return invoice
    
    @staticmethod
    @transaction.atomic
    def cancel_invoice(invoice, user=None):
        """
        Anular una factura
        """
        # Si la factura tiene una orden asociada, devolver stock
        if invoice.sale_order and invoice.sale_order.status == 'CONFIRMED':
            for line in invoice.lines.all():
                from django_erp.sales.models import SaleLine
                sale_line = SaleLine.objects.filter(
                    order=invoice.sale_order,
                    product=line.product
                ).first()
                if sale_line and sale_line.location:
                    WarehouseService.create_entry(
                        product_id=line.product.id,
                        quantity=line.quantity,
                        location_to_id=sale_line.location.id,
                        source_type='MANUAL',
                        source_reference=f"ANULACION-{invoice.number}",
                        note=f"Anulación de factura {invoice.number}",
                        user=user
                    )
        return invoice