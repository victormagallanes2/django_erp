# configuration/context_processors.py
from .models import Company

def current_company(request):
    """
    Context processor para pasar la compañía activa a todos los templates.
    """
    company = getattr(request, 'current_company', None)
    
    if company:
        return {
            'current_company': company,
            'company_name': company.name,
            'company_code': company.code,
            'company_rif': company.rif,
            'company_logo': company.logo.url if company.logo else None,
        }
    return {
        'current_company': None,
        'company_name': '',
        'company_code': '',
        'company_rif': '',
        'company_logo': None,
    }