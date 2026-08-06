# configuration/middleware.py
from django.shortcuts import redirect
from django.urls import reverse
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from .models import Company

class CurrentCompanyMiddleware:
    """
    Middleware para gestionar la compañía activa del usuario.
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
        
        print("🔴 MIDDLEWARE EJECUTADO")
        print(f"   Path: {request.path}")
        print(f"   Usuario autenticado: {request.user.is_authenticated}")
        
        # ✅ Solo para usuarios autenticados
        if not request.user.is_authenticated:
            request.current_company = None
            print("   ⚠️ Usuario no autenticado, current_company = None")
            return

        # ✅ Si el usuario es superusuario
        if request.user.is_superuser:
            print(f"   ✅ Superusuario: {request.user.username}")
            
            # ✅ Si no tiene compañía en sesión, intentar obtener la principal
            if not request.session.get('active_company_id'):
                main_company = Company.get_main_company()
                if main_company:
                    request.session['active_company_id'] = main_company.id
                    request.current_company = main_company
                    print(f"   📌 Usando compañía principal: {main_company.code} - {main_company.name}")
                else:
                    request.current_company = None
                    print("   ⚠️ No hay compañía principal")
            else:
                # ✅ Validar que la compañía en sesión existe y está activa
                try:
                    company = Company.objects.get(
                        id=request.session['active_company_id'],
                        is_active=True
                    )
                    request.current_company = company
                    print(f"   📌 Compañía de sesión: {company.code} - {company.name}")
                except Company.DoesNotExist:
                    # ✅ Si la compañía no existe, limpiar sesión
                    request.session.pop('active_company_id', None)
                    request.current_company = None
                    print("   ⚠️ Compañía de sesión no existe")
            return

        # ✅ Para usuarios normales (no superusuarios)
        user_companies = request.user.companies.all() if hasattr(request.user, 'companies') else Company.objects.none()
        print(f"   👤 Usuario normal: {request.user.username}")
        print(f"   📋 Compañías asignadas: {user_companies.count()}")
        
        if not user_companies.exists():
            request.current_company = None
            print("   ⚠️ Usuario sin compañías asignadas")
            return

        # ✅ Intentar obtener la compañía activa de la sesión
        company_id = request.session.get('active_company_id')
        
        if company_id:
            try:
                company = user_companies.get(id=company_id, is_active=True)
                request.current_company = company
                print(f"   📌 Compañía de sesión: {company.code} - {company.name}")
                return
            except Company.DoesNotExist:
                request.session.pop('active_company_id', None)
                print("   ⚠️ Compañía de sesión no válida")

        # ✅ Si no hay compañía en sesión, usar la primera
        default_company = user_companies.first()
        if default_company:
            request.session['active_company_id'] = default_company.id
            request.current_company = default_company
            print(f"   📌 Usando primera compañía: {default_company.code} - {default_company.name}")
        else:
            request.current_company = None
            print("   ⚠️ No hay compañía predeterminada")
        
        print("🔴 FIN MIDDLEWARE")