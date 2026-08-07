# django_erp/configuration/mixins.py
from django.contrib.admin import ModelAdmin
from django_erp.configuration.models import Company


class CompanyFilterMixin(ModelAdmin):
    """
    Mixin para ModelAdmin que maneja la asignación y filtrado de compañías.
    Mantiene el nombre original para compatibilidad con código existente.
    """
    
    def save_model(self, request, obj, form, change):
        """Asignar la compañía activa al guardar un objeto."""
        self._assign_company(request, obj)
        super().save_model(request, obj, form, change)
    
    def save_formset(self, request, form, formset, change):
        """Asignar la compañía activa a todos los objetos en un formset (inlines)."""
        instances = formset.save(commit=False)
        company = self._get_active_company(request)
        
        for instance in instances:
            if hasattr(instance, 'company') and not instance.company_id:
                instance.company = company
            instance.save()
        
        formset.save_m2m()
        for obj in formset.deleted_objects:
            obj.delete()
    
    def get_queryset(self, request):
        """
        Filtrar el queryset por la compañía activa.
        Los superusuarios ven todas las compañías.
        """
        queryset = super().get_queryset(request)
        
        # Los superusuarios ven todo
        if request.user.is_superuser:
            return queryset
        
        # Usuarios normales: filtrar por su compañía
        company = self._get_active_company(request)
        if company and hasattr(queryset.model, 'company'):
            return queryset.filter(company=company)
        
        return queryset
    
    def _assign_company(self, request, obj):
        """Asignar la compañía activa al objeto si tiene campo company."""
        if hasattr(obj, 'company') and not obj.company_id:
            company = self._get_active_company(request)
            if company:
                obj.company = company
    
    def _get_active_company(self, request):
        """Obtener la compañía activa del request o fallback."""
        # 1. Intentar obtener del request (middleware)
        company = getattr(request, 'current_company', None)
        
        # 2. Si no hay, intentar de la sesión
        if not company and request.session.get('active_company_id'):
            try:
                company = Company.objects.get(
                    id=request.session['active_company_id'],
                    is_active=True
                )
            except Company.DoesNotExist:
                pass
        
        # 3. Fallback: obtener la compañía principal
        if not company:
            company = Company.get_main_company()
        
        # 4. Último fallback: obtener cualquier compañía activa
        if not company:
            company = Company.objects.filter(is_active=True).first()
        
        return company


class CompanyInlineMixin:
    """
    Mixin para Inlines (TabularInline, StackedInline) que maneja la asignación 
    de compañía. NO hereda de ModelAdmin para evitar conflictos.
    """
    
    def save_formset(self, request, form, formset, change):
        """Asignar la compañía activa a todos los objetos en un formset."""
        instances = formset.save(commit=False)
        company = self._get_active_company(request)
        
        for instance in instances:
            if hasattr(instance, 'company') and not instance.company_id:
                instance.company = company
            instance.save()
        
        formset.save_m2m()
        for obj in formset.deleted_objects:
            obj.delete()
    
    def _get_active_company(self, request):
        """Obtener la compañía activa del request o fallback."""
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
        
        if not company:
            company = Company.objects.filter(is_active=True).first()
        
        return company