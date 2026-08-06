# django_erp/context_processors.py

import json
from decimal import Decimal
from django.core.serializers.json import DjangoJSONEncoder
from django_erp.configuration.models import Company, ExchangeRate

def erp_config(request):
    """
    Context processor para pasar configuración del ERP a todos los templates
    """
    
    company = getattr(request, 'current_company', None)
    
    rate = None
    if company:
        try:
            rate = ExchangeRate.get_today_rate('USD', 'BS', company)
        except Exception as e:
            print(f"⚠️ Error obteniendo tasa de cambio: {e}")
            rate = None
    
    available_companies = []
    
    if request.user.is_authenticated:
        if request.user.is_superuser:
            companies_qs = Company.objects.filter(is_active=True)
        else:
            companies_qs = request.user.companies.filter(is_active=True)
        
        for comp in companies_qs:
            available_companies.append({
                'id': comp.id,
                'name': comp.name,
                'code': comp.code,
                'change_url': f"{request.path}?company_id={comp.id}"
            })
    
    # ✅ Para depuración
    print(f"📋 Compañías disponibles: {len(available_companies)}")
    for c in available_companies:
        print(f"   - {c['code']}: {c['name']}")
    
    return {
        'ERP_CONFIG': {
            'tax_rate': float(company.tax_rate) if company else 16.0,
            'exchange_rate': float(rate) if rate else 0,
            'company_name': company.name if company else '',
            'company_rif': company.rif if company else '',
            'currency_symbol': '$',
        },
        'current_company': company,
        'available_companies': available_companies,  # ← Lista, no JSON
    }