# django_erp/configuration/mixins.py
from django.contrib.admin import ModelAdmin
from django_erp.configuration.models import Company
import logging

logger = logging.getLogger(__name__)


class CompanyFilterMixin(ModelAdmin):
    """
    Mixin para ModelAdmin que maneja la asignación, filtrado de compañías
    y ahora también inyecta ERP_CONFIG al contexto.
    """
    
    def changeform_view(self, request, object_id=None, form_url='', extra_context=None):
        """Inyectar ERP_CONFIG al contexto del formulario"""
        extra_context = extra_context or {}
        from .context_processors import erp_config
        erp_context = erp_config(request)
        extra_context.update(erp_context)
        return super().changeform_view(request, object_id, form_url, extra_context)
    
    def save_model(self, request, obj, form, change):
        """Asignar la compañía activa al guardar un objeto."""
        print(f"🔴 ===== MIXIN: save_model =====")
        print(f"   Modelo: {obj.__class__.__name__}")
        
        # ✅ FORZAR ASIGNACIÓN - Verificar si el modelo tiene campo company
        company = self._get_active_company(request)
        
        if company:
            # ✅ Verificar si el modelo tiene el campo 'company' usando _meta
            from django.db import models
            has_company_field = any(
                field.name == 'company' 
                for field in obj._meta.get_fields()
            )
            
            if has_company_field:
                obj.company = company
                print(f"   ✅ Compañía asignada: {company.code} (ID: {company.id})")
            else:
                print(f"   ⚠️ El modelo {obj.__class__.__name__} no tiene campo 'company'")
        else:
            print(f"   ❌ No se encontró compañía activa")
        
        print(f"   company_id después de asignar: {getattr(obj, 'company_id', None)}")
        print("🔴 ===== FIN MIXIN save_model =====")
        
        super().save_model(request, obj, form, change)
    
    def save_formset(self, request, form, formset, change):
        """Asignar la compañía activa a todos los objetos en un formset."""
        print(f"🔴 ===== MIXIN: save_formset =====")
        
        instances = formset.save(commit=False)
        print(f"   Instancias en formset: {len(instances)}")
        
        company = self._get_active_company(request)
        print(f"   Compañía obtenida: {company.code if company else 'NINGUNA'}")
        
        for instance in instances:
            # ✅ Verificar si el modelo tiene el campo 'company' usando _meta
            from django.db import models
            has_company_field = any(
                field.name == 'company' 
                for field in instance._meta.get_fields()
            )
            
            if has_company_field:
                instance.company = company
                print(f"   ✅ company_id asignado a {instance.__class__.__name__}: {instance.company_id}")
        
        super().save_formset(request, form, formset, change)
        print("🔴 ===== FIN MIXIN save_formset =====")
    
    def get_queryset(self, request):
        """Filtrar por compañía activa."""
        queryset = super().get_queryset(request)
        company = self._get_active_company(request)
        
        if company:
            # ✅ Verificar si el modelo tiene el campo 'company' usando _meta
            from django.db import models
            has_company_field = any(
                field.name == 'company' 
                for field in queryset.model._meta.get_fields()
            )
            
            if has_company_field:
                print(f"🔍 Filtrando {queryset.model.__name__} por compañía: {company.code}")
                return queryset.filter(company=company)
        
        print(f"⚠️ No hay compañía activa para {queryset.model.__name__}, devolviendo vacío")
        return queryset.none()
    
    def _get_active_company(self, request):
        """Obtener la compañía activa del request o fallback."""
        print(f"🔴 ===== _get_active_company =====")
        
        # 1. Intentar obtener del request (middleware)
        company = getattr(request, 'current_company', None)
        print(f"   1. Del request.current_company: {company.code if company else 'None'}")
        
        # 2. Si no hay, intentar de la sesión
        if not company and request.session.get('active_company_id'):
            try:
                company = Company.objects.get(
                    id=request.session['active_company_id'],
                    is_active=True
                )
                print(f"   2. De la sesión (ID: {request.session['active_company_id']}): {company.code if company else 'None'}")
            except Company.DoesNotExist:
                print(f"   2. Compañía de sesión no encontrada")
                pass
        
        # 3. Fallback: obtener la compañía principal
        if not company:
            company = Company.get_main_company()
            print(f"   3. Fallback (compañía principal): {company.code if company else 'None'}")
        
        # 4. Último fallback: obtener cualquier compañía activa
        if not company:
            company = Company.objects.filter(is_active=True).first()
            print(f"   4. Último fallback (cualquier activa): {company.code if company else 'None'}")
        
        print(f"🔴 ===== FIN _get_active_company: {company.code if company else 'NINGUNA'} =====")
        return company