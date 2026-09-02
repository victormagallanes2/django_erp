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


class CurrencyService:
    """Servicio de conversión de monedas"""
    
    @staticmethod
    def get_base_currency():
        """Obtener moneda base del sistema"""
        return Currency.get_base()
    
    @staticmethod
    def get_base_symbol():
        """Obtener símbolo de la moneda base"""
        base = Currency.get_base()
        return base.symbol if base else '$'
    
    @staticmethod
    def get_local_currency():
        """Obtener moneda local (BS para Venezuela)"""
        try:
            return Currency.objects.get(code='BS')
        except Currency.DoesNotExist:
            return None
    
    @staticmethod
    def get_local_symbol():
        """Obtener símbolo de la moneda local"""
        local = CurrencyService.get_local_currency()
        return local.symbol if local else 'Bs.'
    
    @staticmethod
    def convert_to_local(amount_usd):
        """Convertir USD a moneda local"""
        try:
            rate = ExchangeRate.get_today_rate('USD', 'BS')
            return amount_usd * rate
        except:
            return amount_usd
    
    @staticmethod
    def get_today_rate():
        """Obtener tasa del día"""
        try:
            return ExchangeRate.get_today_rate('USD', 'BS')
        except:
            return None
    
    @staticmethod
    def format_price(price, currency_code=None):
        """Formatear precio con símbolo de moneda"""
        if currency_code is None:
            base = Currency.get_base()
            currency_code = base.code if base else 'USD'
        
        try:
            currency = Currency.objects.get(code=currency_code)
            return f"{currency.symbol} {price:.{currency.decimal_places}f}"
        except Currency.DoesNotExist:
            return f"${price:.2f}"

    @staticmethod
    def get_historical_rate(from_code, to_code, date, company=None):
        """
        Obtener la tasa de cambio vigente en una fecha específica
        Útil para reportes contables de fechas pasadas
        """
        return ExchangeRate.get_rate(from_code, to_code, company, date)
    
    @staticmethod
    def get_rate_history(from_code, to_code, company=None, days=30):
        """
        Obtener el historial de tasas de cambio
        Útil para gráficos y reportes
        """
        return ExchangeRate.get_historical_rates(from_code, to_code, company, days)
    
    @staticmethod
    def get_rate_change_summary(from_code, to_code, company=None, days=30):
        """
        Obtener resumen de cambios de tasa
        Útil para auditoría
        """
        if company is None:
            company = Company.get_active()
        
        if not company:
            return None
        
        from_currency = Currency.objects.get(code=from_code)
        to_currency = Currency.objects.get(code=to_code)
        
        rates = ExchangeRate.objects.filter(
            company=company,
            from_currency=from_currency,
            to_currency=to_currency
        ).order_by('effective_date')
        
        if not rates.exists():
            return None
        
        first = rates.first()
        last = rates.last()
        
        return {
            'first_rate': first.rate,
            'first_date': first.effective_date,
            'last_rate': last.rate,
            'last_date': last.effective_date,
            'change': last.rate - first.rate,
            'change_percent': ((last.rate - first.rate) / first.rate) * 100,
            'total_changes': rates.count(),
            'last_change': last,
            'history': rates
        }