# django_erp/accounting/services.py
from decimal import Decimal
from datetime import date
from django.core.exceptions import ValidationError
from django_erp.configuration.models import Company
from .models import Tax, TaxRate


class TaxService:
    """
    Servicio centralizado para gestionar impuestos desde el módulo de contabilidad.
    """
    
    @staticmethod
    def get_current_rate(tax_code='VAT', company=None, date_obj=None):
        """
        Obtiene la tasa de impuesto vigente para una compañía en una fecha específica.
        
        Args:
            tax_code (str): Código del impuesto (ej: 'VAT', 'ISLR')
            company (Company): Compañía para la cual obtener la tasa
            date_obj (date): Fecha de vigencia (por defecto: hoy)
        
        Returns:
            Decimal: Tasa de impuesto como decimal (ej: 16.00 para 16%)
        """
        if date_obj is None:
            date_obj = date.today()
        
        # Si no se proporciona compañía, obtener la activa
        if company is None:
            company = Company.get_active()
            if not company:
                return Decimal('0.00')
        
        try:
            tax = Tax.objects.get(code=tax_code, is_active=True)
        except Tax.DoesNotExist:
            return Decimal('0.00')
        
        rate_obj = TaxRate.objects.filter(
            tax=tax,
            company=company,
            effective_date__lte=date_obj,
            tax__is_active=True
        ).order_by(
            '-is_default',  # Priorizar la tasa por defecto
            '-effective_date'
        ).first()
        
        return rate_obj.rate if rate_obj else Decimal('0.00')
    
    @staticmethod
    def get_current_vat_rate(company=None, date_obj=None):
        """
        Método conveniente para obtener la tasa de IVA actual.
        """
        return TaxService.get_current_rate('VAT', company, date_obj)
    
    @staticmethod
    def get_tax_by_code(tax_code):
        """
        Obtiene un impuesto por su código.
        """
        try:
            return Tax.objects.get(code=tax_code, is_active=True)
        except Tax.DoesNotExist:
            return None
    
    @staticmethod
    def get_rates_history(tax_code='VAT', company=None, days=30):
        """
        Obtiene el historial de tasas de impuesto para los últimos N días.
        Útil para gráficos y reportes.
        """
        from datetime import timedelta
        
        if company is None:
            company = Company.get_active()
            if not company:
                return []
        
        try:
            tax = Tax.objects.get(code=tax_code, is_active=True)
        except Tax.DoesNotExist:
            return []
        
        start_date = date.today() - timedelta(days=days)
        
        rates = TaxRate.objects.filter(
            tax=tax,
            company=company,
            effective_date__gte=start_date
        ).order_by('effective_date')
        
        return rates
    
    @staticmethod
    def calculate_tax(amount, tax_code='VAT', company=None, date_obj=None):
        """
        Calcula el monto de impuesto para un subtotal.
        
        Args:
            amount (Decimal): Subtotal sobre el cual calcular el impuesto
            tax_code (str): Código del impuesto
            company (Company): Compañía para la cual calcular
            date_obj (date): Fecha de vigencia
        
        Returns:
            tuple: (tasa, monto_impuesto)
        """
        rate = TaxService.get_current_rate(tax_code, company, date_obj)
        tax_amount = amount * (rate / Decimal('100'))
        return rate, tax_amount
    
    @staticmethod
    def calculate_vat(amount, company=None, date_obj=None):
        """
        Método conveniente para calcular el IVA.
        """
        return TaxService.calculate_tax(amount, 'VAT', company, date_obj)
    
    @staticmethod
    def get_default_tax_for_company(company=None):
        """
        Obtiene el impuesto por defecto para una compañía.
        """
        if company is None:
            company = Company.get_active()
        
        if not company:
            return None
        
        # Buscar el impuesto más común (IVA)
        try:
            return Tax.objects.get(code='VAT', is_active=True)
        except Tax.DoesNotExist:
            return Tax.objects.filter(is_active=True).first()
    
    @staticmethod
    def create_or_update_tax_rate(tax_code, company, rate, effective_date, is_default=False, note=''):
        """
        Crea o actualiza una tasa de impuesto.
        """
        tax = TaxService.get_tax_by_code(tax_code)
        if not tax:
            raise ValidationError(f"Impuesto con código '{tax_code}' no encontrado.")
        
        tax_rate, created = TaxRate.objects.update_or_create(
            tax=tax,
            company=company,
            effective_date=effective_date,
            defaults={
                'rate': rate,
                'is_default': is_default,
                'note': note,
            }
        )
        
        return tax_rate, created