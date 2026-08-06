# django_erp/context_processors.py
from django_erp.configuration.models import Company, ExchangeRate
from django.core.serializers.json import DjangoJSONEncoder
import json

def erp_config(request):
    """Context processor para pasar configuración del ERP a todos los templates"""

    company = getattr(request, 'current_company', None)

    # ✅ Obtener tasa de cambio
    rate = ExchangeRate.get_today_rate('USD', 'BS')

    # ✅ Preparar lista de compañías para el usuario
    available_companies = []
    # Si el usuario está autenticado y es superusuario o tiene compañías asignadas
    if request.user.is_authenticated:
        if request.user.is_superuser:
            # Superusuario ve TODAS las compañías activas
            companies_qs = Company.objects.filter(is_active=True)
        else:
            # Usuario normal ve sus compañías asignadas
            companies_qs = request.user.companies.filter(is_active=True)

        # Construir lista para el dropdown
        for comp in companies_qs:
            available_companies.append({
                'id': comp.id,
                'name': comp.name,
                'code': comp.code,
                # ✅ URL para cambiar de compañía (usamos la misma página)
                'change_url': f"{request.path}?company_id={comp.id}"
            })

    # ✅ Crear un JSON seguro para pasarlo a JavaScript
    available_companies_json = json.dumps(available_companies, cls=DjangoJSONEncoder)

    return {
        'ERP_CONFIG': {
            'tax_rate': float(company.tax_rate) if company else 16.0,
            'exchange_rate': float(rate) if rate else 0,
            'company_name': company.name if company else '',
            'company_rif': company.rif if company else '',
            'currency_symbol': '$',
        },
        # ✅ Nuevas variables para el switcher
        'current_company': company,
        'available_companies': available_companies,
        'available_companies_json': available_companies_json,
    }