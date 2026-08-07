# django_erp/configuration/middleware.py
from django.shortcuts import redirect
from django.contrib import messages
from .models import Company

class CurrentCompanyMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        self.process_request(request)
        response = self.get_response(request)
        return response

    def process_request(self, request):
        if not request.user.is_authenticated:
            request.current_company = None
            return

        # ✅ Si viene company_id en GET, cambiar compañía
        company_id = request.GET.get('company_id')
        if company_id:
            try:
                company = Company.objects.get(id=company_id, is_active=True)
                # Verificar acceso
                if request.user.is_superuser or company in request.user.companies.all():
                    request.session['active_company_id'] = company.id
                    request.current_company = company
                    # ✅ IMPORTANTE: No hacer redirect aquí, solo guardar en sesión
                    return
            except Company.DoesNotExist:
                pass

        # ✅ Si hay compañía en sesión
        if request.session.get('active_company_id'):
            try:
                company = Company.objects.get(
                    id=request.session['active_company_id'],
                    is_active=True
                )
                # Verificar acceso
                if request.user.is_superuser or company in request.user.companies.all():
                    request.current_company = company
                    return
                else:
                    request.session.pop('active_company_id', None)
            except Company.DoesNotExist:
                request.session.pop('active_company_id', None)

        # ✅ Si es superusuario, usar compañía principal
        if request.user.is_superuser:
            main_company = Company.get_main_company()
            if main_company:
                request.session['active_company_id'] = main_company.id
                request.current_company = main_company
                return

        # ✅ Usuario normal, usar primera compañía asignada
        user_companies = request.user.companies.filter(is_active=True)
        if user_companies.exists():
            company = user_companies.first()
            request.session['active_company_id'] = company.id
            request.current_company = company
            return

        request.current_company = None