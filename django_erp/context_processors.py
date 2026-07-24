# django_erp/context_processors.py
from django_erp.configuration.models import Company, ExchangeRate


def erp_config(request):
    """Context processor para pasar configuración del ERP a todos los templates"""
    
    # ✅ Obtener empresa activa
    company = Company.get_active()
    
    # ✅ Obtener tasa de cambio
    rate = ExchangeRate.get_today_rate('USD', 'BS')
    
    return {
        'ERP_CONFIG': {
            'tax_rate': float(company.tax_rate) if company else 16.0,
            'exchange_rate': float(rate) if rate else 0,
            'company_name': company.name if company else '',
            'company_rif': company.rif if company else '',
            'currency_symbol': '$',
        }
    }