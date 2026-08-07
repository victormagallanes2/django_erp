# django_erp/configuration/context_processors.py
import json
from django.core.serializers.json import DjangoJSONEncoder
from django_erp.configuration.models import Company, ExchangeRate

def erp_config(request):
    company = getattr(request, 'current_company', None)
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
    
    # ✅ Asegurar que el JSON sea válido
    try:
        companies_json = json.dumps(available_companies, cls=DjangoJSONEncoder)
    except:
        companies_json = '[]'
    
    return {
        'available_companies': available_companies,
        'available_companies_json': companies_json,
        'current_company': company,
        'ERP_CONFIG': {
            'tax_rate': float(company.tax_rate) if company else 16.0,
            'exchange_rate': float(ExchangeRate.get_today_rate('USD', 'BS')) or 0,
            'company_name': company.name if company else '',
            'company_rif': company.rif if company else '',
            'currency_symbol': '$',
        }
    }