# django_erp/configuration/context_processors.py
import json
import logging
from django.core.serializers.json import DjangoJSONEncoder
from django_erp.configuration.models import Company
from django_erp.accounting.models import ExchangeRate
from django_erp.accounting.services import TaxService

logger = logging.getLogger(__name__)


def erp_config(request):
    # ✅ Usar la compañía que el middleware asignó
    company = getattr(request, 'current_company', None)

    if not company and request.session.get('active_company_id'):
        try:
            company = Company.objects.get(
                id=request.session['active_company_id'],
                is_active=True
            )
        except Company.DoesNotExist:
            pass

    if not company:
        company = Company.get_main_company()

    # ============================================================
    # Compañías disponibles para el usuario
    # ============================================================
    available_companies = []
    
    if request.user.is_authenticated:
        if request.user.is_superuser:
            companies_qs = Company.objects.filter(is_active=True)
        else:
            companies_qs = request.user.companies.filter(is_active=True)
        
        for comp in companies_qs.order_by('code'):
            available_companies.append({
                'id': comp.id,
                'name': comp.name,
                'code': comp.code,
                # URL de cambio: misma página con ?company_id=X
                'change_url': f"{request.path}?company_id={comp.id}",
            })

    # ============================================================
    # Tasa de cambio y datos de la compañía activa
    # ============================================================
    rate = ExchangeRate.get_today_rate('USD', 'BS')
    
    tax_rate = 0.0
    company_name = ""
    company_rif = ""
    
    if company:
        tax_rate = float(TaxService.get_current_vat_rate(company))
        company_name = company.name
        company_rif = company.rif

    erp_config_dict = {
        'tax_rate': tax_rate,
        'exchange_rate': float(rate) if rate else 0,
        'company_name': company_name,
        'company_rif': company_rif,
        'currency_symbol': '$',
    }

    # Serializar a JSON para inyectar en el template
    try:
        companies_json = json.dumps(available_companies, cls=DjangoJSONEncoder)
        erp_config_json = json.dumps(erp_config_dict)
    except Exception:
        companies_json = '[]'
        erp_config_json = '{}'

    return {
        'available_companies': available_companies,
        'available_companies_json': companies_json,
        'current_company': company,
        'ERP_CONFIG': erp_config_dict,
        'ERP_CONFIG_JSON': erp_config_json,
    }