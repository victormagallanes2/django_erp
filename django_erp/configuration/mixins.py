# django_erp/configuration/mixins.py
from django.contrib.admin import ModelAdmin
from django_erp.configuration.models import Company
import logging

logger = logging.getLogger(__name__)


class CompanyFilterMixin(ModelAdmin):
    """
    Mixin para ModelAdmin que maneja la asignación y filtrado de compañías.
    """
    
    def save_model(self, request, obj, form, change):
        """Asignar la compañía activa al guardar un objeto."""
        print(f"🔴 ===== MIXIN: save_model =====")
        print(f"   Modelo: {obj.__class__.__name__}")
        print(f"   Tiene company: {hasattr(obj, 'company')}")
        print(f"   company_id actual: {getattr(obj, 'company_id', 'NO TIENE')}")
        
        # ✅ FORZAR la asignación de compañía (sin condiciones)
        company = self._get_active_company(request)
        if company and hasattr(obj, 'company'):
            obj.company = company
            print(f"   ✅ Compañía asignada: {company.code} (ID: {company.id})")
        elif company:
            print(f"   ⚠️ El objeto no tiene campo 'company'")
        else:
            print(f"   ❌ No se encontró compañía activa")
        
        print(f"   company_id después de asignar: {obj.company_id}")
        print("🔴 ===== FIN MIXIN save_model =====")
        
        # Llamar a super() para que Django guarde el objeto
        super().save_model(request, obj, form, change)
    
    def save_formset(self, request, form, formset, change):
        """
        Asignar la compañía activa a todos los objetos en un formset (inlines)
        ANTES de que Django los guarde.
        """
        print(f"🔴 ===== MIXIN: save_formset =====")
        
        # 1. Obtenemos las instancias del formset sin guardarlas aún
        instances = formset.save(commit=False)
        print(f"   Instancias en formset: {len(instances)}")
        
        # 2. Asignamos la compañía a cada instancia que lo necesite
        company = self._get_active_company(request)
        print(f"   Compañía obtenida: {company.code if company else 'NINGUNA'}")
        
        for instance in instances:
            if hasattr(instance, 'company'):
                print(f"   Asignando compañía a: {instance.__class__.__name__}")
                instance.company = company
                print(f"   ✅ company_id asignado: {instance.company_id}")
        
        # 3. Llamamos al save_formset de la clase padre
        super().save_formset(request, form, formset, change)
        print("🔴 ===== FIN MIXIN save_formset =====")
    
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
        """Método obsoleto, ahora se hace en save_model directamente."""
        pass
    
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