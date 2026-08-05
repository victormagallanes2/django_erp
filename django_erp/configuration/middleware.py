# configuration/middleware.py
from django.shortcuts import redirect
from django.urls import reverse
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from .models import Company

class CurrentCompanyMiddleware:
    """
    Middleware para gestionar la compañía activa del usuario.
    Similar al comportamiento de Odoo con múltiples compañías.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Procesar la solicitud
        self.process_request(request)
        response = self.get_response(request)
        return response

    def process_request(self, request):
        """Establece la compañía activa en cada petición"""
        
        # ✅ Solo para usuarios autenticados
        if not request.user.is_authenticated:
            request.current_company = None
            return

        # ✅ Si el usuario es superusuario, puede ver todas las compañías
        if request.user.is_superuser:
            # ✅ Si no tiene compañía en sesión, intentar obtener la principal
            if not request.session.get('active_company_id'):
                main_company = Company.get_main_company()
                if main_company:
                    request.session['active_company_id'] = main_company.id
                    request.current_company = main_company
                else:
                    request.current_company = None
            else:
                # ✅ Validar que la compañía en sesión existe y está activa
                try:
                    company = Company.objects.get(
                        id=request.session['active_company_id'],
                        is_active=True
                    )
                    request.current_company = company
                except Company.DoesNotExist:
                    # ✅ Si la compañía no existe, limpiar sesión
                    request.session.pop('active_company_id', None)
                    request.current_company = None
            return

        # ✅ Para usuarios normales (no superusuarios)
        # ✅ Obtener las compañías asignadas al usuario
        # Nota: Asumimos que el modelo User tiene una relación ManyToMany con Company
        user_companies = request.user.companies.all() if hasattr(request.user, 'companies') else Company.objects.none()
        
        if not user_companies.exists():
            # ✅ Si el usuario no tiene compañías asignadas
            request.current_company = None
            return

        # ✅ Intentar obtener la compañía activa de la sesión
        company_id = request.session.get('active_company_id')
        
        if company_id:
            try:
                company = user_companies.get(id=company_id, is_active=True)
                request.current_company = company
                return
            except Company.DoesNotExist:
                # ✅ La compañía en sesión no es válida o no está activa
                request.session.pop('active_company_id', None)

        # ✅ Si no hay compañía en sesión o no es válida, usar la primera
        default_company = user_companies.first()
        if default_company:
            request.session['active_company_id'] = default_company.id
            request.current_company = default_company
        else:
            request.current_company = None