# django_erp/context_processors.py
from django_erp.configuration.models import Company, ExchangeRate
from django.core.serializers.json import DjangoJSONEncoder
import json
import logging

logger = logging.getLogger(__name__)

def erp_config(request):
    """Context processor para pasar configuración del ERP a todos los templates"""
    
    print("=" * 80)
    print("🔴 CONTEXT PROCESSOR EJECUTADO")
    print("=" * 80)
    
    company = getattr(request, 'current_company', None)
    print(f"   Compañía actual: {company}")
    
    # ✅ Obtener tasa de cambio
    rate = ExchangeRate.get_today_rate('USD', 'BS')
    print(f"   Tasa de cambio: {rate}")
    
    # ✅ Preparar lista de compañías para el usuario
    available_companies = []
    
    print(f"   Usuario autenticado: {request.user.is_authenticated}")
    
    if request.user.is_authenticated:
        print(f"   Usuario: {request.user.username}")
        print(f"   Es superusuario: {request.user.is_superuser}")
        
        if request.user.is_superuser:
            # Superusuario ve TODAS las compañías activas
            companies_qs = Company.objects.filter(is_active=True)
            print(f"   SUPERUSUARIO: Ve {companies_qs.count()} compañías")
        else:
            # Usuario normal ve sus compañías asignadas
            companies_qs = request.user.companies.filter(is_active=True)
            print(f"   USUARIO NORMAL: Tiene {companies_qs.count()} compañías asignadas")
        
        # Construir lista para el dropdown
        for comp in companies_qs:
            print(f"   ✅ Agregando compañía: {comp.code} - {comp.name}")
            available_companies.append({
                'id': comp.id,
                'name': comp.name,
                'code': comp.code,
                'change_url': f"{request.path}?company_id={comp.id}"
            })
    else:
        print("   ⚠️ Usuario NO autenticado")
    
    print(f"   📊 TOTAL DE COMPAÑÍAS EN EL CONTEXTO: {len(available_companies)}")
    print("=" * 80)
    
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
        'current_company': company,
        'available_companies': available_companies,
        'available_companies_json': available_companies_json,
        # ✅ Agregamos una variable de prueba para verificar que el context processor funciona
        'TEST_VAR': 'El context processor funciona!',
    }