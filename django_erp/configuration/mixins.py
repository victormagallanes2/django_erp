# django_erp/configuration/mixins.py

from django.contrib.admin import ModelAdmin

class CompanyFilterMixin(ModelAdmin):
    """
    Mixin para ModelAdmin que filtra automáticamente los objetos por la compañía activa.
    También asigna automáticamente la compañía activa al crear nuevos objetos.
    """
    
    def get_queryset(self, request):
        """Filtrar el queryset por la compañía activa"""
        queryset = super().get_queryset(request)
        
        # ✅ Obtener la compañía activa
        company = getattr(request, 'current_company', None)
        
        if company:
            # ✅ Filtrar por compañía
            return queryset.filter(company=company)
        
        # ✅ Si no hay compañía activa, devolver queryset vacío (o todos si es superusuario)
        if request.user.is_superuser:
            return queryset
        return queryset.none()
    
    def save_model(self, request, obj, form, change):
        """Asignar automáticamente la compañía activa al crear un objeto"""
        print(f"🔴 CompanyFilterMixin.save_model llamado")
        print(f"   change: {change}")
        print(f"   obj.company_id: {getattr(obj, 'company_id', 'NO EXISTE')}")
        
        if not change:  # Si es un objeto nuevo
            company = getattr(request, 'current_company', None)
            print(f"   company desde request: {company}")
            
            if company and hasattr(obj, 'company'):
                obj.company = company
                print(f"   ✅ Compañía asignada: {company.name} (ID: {company.id})")
            else:
                print(f"   ⚠️ No se pudo asignar compañía automáticamente")
                # ✅ Intentar obtener la compañía activa de otra forma
                from django_erp.configuration.models import Company
                company = Company.get_active()
                if company and hasattr(obj, 'company'):
                    obj.company = company
                    print(f"   ✅ Compañía asignada (fallback): {company.name}")
        
        print(f"   obj.company_id FINAL: {obj.company_id}")
        super().save_model(request, obj, form, change)
    
    def get_form(self, request, obj=None, **kwargs):
        """Pre-seleccionar la compañía activa en el formulario"""
        form = super().get_form(request, obj, **kwargs)
        
        # ✅ Si es un objeto nuevo y el modelo tiene campo 'company'
        if not obj and 'company' in form.base_fields:
            company = getattr(request, 'current_company', None)
            if company:
                form.base_fields['company'].initial = company
                # ✅ Para usuarios normales, hacer el campo de solo lectura
                if not request.user.is_superuser:
                    form.base_fields['company'].disabled = True
        
        return form