# django_erp/configuration/middleware.py
from .models import Company


class CurrentCompanyMiddleware:
    """
    Middleware que determina la compañía activa para cada request.
    
    Prioridad:
    1. ?company_id=X en la URL (cambio explícito → guarda preferencia)
    2. Compañía de la sesión (si el usuario tiene acceso)
    3. Compañía preferida del usuario (user.preferred_company)
    4. Compañía principal (superuser) o primera asignada
    """
    
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        self.process_request(request)
        response = self.get_response(request)
        return response

    def process_request(self, request):
        # Usuario no autenticado
        if not request.user.is_authenticated:
            request.current_company = None
            return

        # ============================================================
        # 1. Cambio explícito vía ?company_id=X
        # ============================================================
        company_id = request.GET.get('company_id')
        if company_id:
            try:
                company = Company.objects.get(id=company_id, is_active=True)
                if self._user_has_access(request.user, company):
                    # ✅ Guardar en sesión
                    request.session['active_company_id'] = company.id
                    request.current_company = company
                    
                    # ✅ Guardar preferencia en el usuario
                    if request.user.preferred_company_id != company.id:
                        request.user.preferred_company = company
                        request.user.save(update_fields=['preferred_company'])
                    
                    return
            except Company.DoesNotExist:
                pass

        # ============================================================
        # 2. Compañía de la sesión
        # ============================================================
        session_company_id = request.session.get('active_company_id')
        if session_company_id:
            try:
                company = Company.objects.get(
                    id=session_company_id,
                    is_active=True
                )
                if self._user_has_access(request.user, company):
                    request.current_company = company
                    return
                else:
                    request.session.pop('active_company_id', None)
            except Company.DoesNotExist:
                request.session.pop('active_company_id', None)

        # ============================================================
        # 3. Compañía preferida del usuario
        # ============================================================
        if request.user.preferred_company_id:
            try:
                company = request.user.preferred_company
                if company and company.is_active and self._user_has_access(request.user, company):
                    request.session['active_company_id'] = company.id
                    request.current_company = company
                    return
            except Company.DoesNotExist:
                pass

        # ============================================================
        # 4. Fallback: compañía por defecto
        # ============================================================
        company = self._get_default_company(request.user)
        if company:
            request.session['active_company_id'] = company.id
            request.current_company = company
        else:
            request.current_company = None

    def _user_has_access(self, user, company):
        """Verifica si el usuario puede operar con esta compañía."""
        if user.is_superuser:
            return True
        return user.companies.filter(id=company.id, is_active=True).exists()

    def _get_default_company(self, user):
        """Compañía por defecto según el tipo de usuario."""
        if user.is_superuser:
            return Company.get_main_company()
        
        user_companies = user.companies.filter(is_active=True)
        if user_companies.exists():
            return user_companies.first()
        
        return None