# sales/services.py - CORREGIDO
from django.db import transaction
from django.core.exceptions import ValidationError
from django.apps import apps
from .models import SaleOrder
from django.db.models import Sum
from django.db.models.functions import TruncDay, TruncMonth, TruncYear
from django.utils import timezone
from decimal import Decimal
from datetime import timedelta
from django_erp.configuration.models import Company


class SaleService:
    """Servicios de ventas - Soporta productos y servicios"""
    
    @staticmethod
    @transaction.atomic
    def confirm_order(order, user=None):
        """✅ Confirmar una orden - Productos físicos y servicios"""
        
        # ✅ Obtener la compañía de la orden o la activa
        company = order.company or Company.get_active()
        if not company:
            raise ValidationError("No hay una compañía asociada a esta orden o activa.")
        
        print(f"🔴 CONFIRMANDO ORDEN {order.number} para compañía {company.code}")
        
        # ============================================================
        # 📦 1. PROCESAR PRODUCTOS Y SERVICIOS
        # ============================================================
        
        for line in order.lines.all():
            if line.product:
                # ✅ Si es servicio, no verificar stock
                if line.product.is_service:
                    print(f"📝 Servicio confirmado: {line.product.name}")
                    continue

                # ✅ Crear movimiento de salida para productos físicos
                if apps.is_installed('django_erp.warehouse'):
                    from django_erp.inventory.services import WarehouseService
                    
                    # ✅ Asegurar que la ubicación tenga compañía
                    location_id = line.location.id if line.location else None
                    if location_id:
                        from django_erp.warehouse.models import Location
                        try:
                            location = Location.objects.get(id=location_id, company=company)
                        except Location.DoesNotExist:
                            # ✅ Si la ubicación no pertenece a la compañía, buscar una por defecto
                            location = Location.objects.filter(company=company, is_active=True).first()
                            if location:
                                location_id = location.id
                                print(f"   ⚠️ Ubicación cambiada a: {location.code}")
                            else:
                                raise ValidationError(f"No hay ubicación disponible para la compañía {company.code}")
                    
                    WarehouseService.create_exit(
                        product_id=line.product.id,
                        quantity=line.quantity,
                        location_from_id=location_id,
                        unit_price=line.unit_price,
                        source_type='SALE',
                        source_reference=order.number,
                        note=f"Venta {order.number} - {order.customer.name}",
                        user=user or order.user,
                        company=company  # ← ✅ PASAR LA COMPAÑÍA
                    )
                else:
                    print(f"ℹ️ Warehouse no instalado. No se reduce stock para {line.product.name}")
            else:
                print(f"📝 Servicio confirmado: {line.product_name or line.description or 'Servicio'}")
        
        # ============================================================
        # ✅ 2. ACTUALIZAR ESTADO DE LA ORDEN
        # ============================================================
        
        order.status = 'CONFIRMED'
        order.save()
        
        # ============================================================
        # 💰 3. REGISTRAR EN CAJA
        # ============================================================
        
        if apps.is_installed('django_erp.sales'):
            from .models import CashTransaction
            from .helpers import get_open_register
            
            try:
                # 🔍 Obtener la caja abierta del usuario
                register = get_open_register(user or order.user)
                
                # 📝 Crear transacción de caja
                CashTransaction.objects.create(
                    register=register,
                    type='SALE',
                    amount=order.total,
                    description=f"Venta {order.number} - {order.customer.name}",
                    reference=order.number,
                    user=user or order.user,
                    company=company,  # ← ✅ ASIGNAR COMPAÑÍA A LA TRANSACCIÓN
                )
                
                # 🔄 Recalcular totales de la caja
                register.calculate_totals()
                
                print(f"✅ Transacción registrada en caja {register.number}")
                
            except ValidationError as e:
                print(f"⚠️ Error al registrar en caja: {e}")
                raise ValidationError(f"❌ Error al registrar en caja: {str(e)}")
        
        # ============================================================
        # 📄 4. GENERAR FACTURA (SI ESTÁ INSTALADO INVOICING)
        # ============================================================
        
        if apps.is_installed('django_erp.invoicing'):
            try:
                from django_erp.invoicing.services import InvoiceService
                InvoiceService.create_invoice_from_sale_order(order.id, user or order.user)
                print(f"✅ Factura generada para orden {order.number}")
            except Exception as e:
                print(f"⚠️ Error al generar factura: {e}")
                # No detener el proceso si falla la factura
        
        return order
    
    @staticmethod
    @transaction.atomic
    def cancel_order(order, user=None, old_status=None):
        """Cancelar una orden"""
        
        if order.status in ['DELIVERED', 'CANCELLED']:
            raise ValidationError("No se puede cancelar una orden entregada o ya cancelada")
        
        if old_status == 'CONFIRMED':
            for line in order.lines.all():
                # ✅ Solo devolver stock si es producto físico
                if line.product and not line.product.is_service:
                    if apps.is_installed('django_erp.warehouse'):
                        from django_erp.warehouse.services import WarehouseService
                        WarehouseService.create_entry(
                            product_id=line.product.id,
                            quantity=line.quantity,
                            location_to_id=line.location.id if line.location else None,
                            source_type='MANUAL',
                            source_reference=f"CANCEL-{order.number}",
                            note=f"Cancelación de venta {order.number}",
                            user=user or order.user,
                            company=order.company  # ← ✅ PASAR LA COMPAÑÍA
                        )
        
        return order
    
    @staticmethod
    @transaction.atomic
    def deliver_order(order, user=None):
        """Entregar una orden"""
        if order.status != 'CONFIRMED':
            raise ValidationError("Solo se pueden entregar órdenes confirmadas")
        return order


class SaleReportService:
    """Servicio para generar reportes de ventas."""

    @staticmethod
    def get_totals_by_period(period_type='day', days_back=30, company=None):
        """
        Obtiene el total de ventas agrupadas por un período específico.

        Args:
            period_type (str): 'day', 'month', 'year'
            days_back (int): Número de días hacia atrás para el filtro (solo para 'day').
            company (Company): Compañía para filtrar (opcional)

        Returns:
            tuple: (list_of_labels, list_of_totals)
        """
        # ✅ Filtrar órdenes confirmadas y entregadas (excluir borradores y canceladas)
        queryset = SaleOrder.objects.filter(status__in=['CONFIRMED', 'DELIVERED'])

        # ✅ FILTRAR POR COMPAÑÍA SI SE PROPORCIONA
        if company:
            queryset = queryset.filter(company=company)
        else:
            # ✅ Si no se proporciona compañía, usar la activa
            company = Company.get_active()
            if company:
                queryset = queryset.filter(company=company)

        # Definir el rango de fechas y el truncado según el período
        if period_type == 'day':
            start_date = timezone.now() - timedelta(days=days_back)
            queryset = queryset.filter(date__gte=start_date)
            trunc_function = TruncDay('date')
            label_format = '%d-%m'
        elif period_type == 'month':
            start_date = timezone.now() - timedelta(days=365)
            queryset = queryset.filter(date__gte=start_date)
            trunc_function = TruncMonth('date')
            label_format = 'b Y'
        elif period_type == 'year':
            start_date = timezone.now() - timedelta(days=3650)
            queryset = queryset.filter(date__gte=start_date)
            trunc_function = TruncYear('date')
            label_format = 'Y'
        else:
            raise ValueError("Tipo de período no soportado")

        # Agrupar y sumar
        report_data = (
            queryset
            .annotate(period=trunc_function)
            .values('period')
            .annotate(total=Sum('total'))
            .order_by('period')
        )

        labels = []
        totals = []

        for entry in report_data:
            if entry['period']:
                labels.append(entry['period'].strftime(label_format))
                totals.append(float(entry['total']))
            else:
                labels.append('Fecha desconocida')
                totals.append(0.0)

        return labels, totals

    @staticmethod
    def get_grand_totals(company=None):
        """
        Calcula los totales de ventas de hoy, este mes y este año.

        Args:
            company (Company): Compañía para filtrar (opcional)

        Returns:
            dict: Totales de ventas
        """
        today = timezone.now().date()
        first_day_of_month = today.replace(day=1)
        first_day_of_year = today.replace(month=1, day=1)

        # ✅ FILTRAR POR COMPAÑÍA
        queryset = SaleOrder.objects.filter(status__in=['CONFIRMED', 'DELIVERED'])

        if company:
            queryset = queryset.filter(company=company)
        else:
            # ✅ Si no se proporciona compañía, usar la activa
            company = Company.get_active()
            if company:
                queryset = queryset.filter(company=company)

        # Calcular totales
        sales_today = queryset.filter(date=today).aggregate(Sum('total'))['total__sum'] or Decimal('0.00')
        sales_this_month = queryset.filter(date__gte=first_day_of_month).aggregate(Sum('total'))['total__sum'] or Decimal('0.00')
        sales_this_year = queryset.filter(date__gte=first_day_of_year).aggregate(Sum('total'))['total__sum'] or Decimal('0.00')

        return {
            'today': float(sales_today),
            'this_month': float(sales_this_month),
            'this_year': float(sales_this_year),
        }