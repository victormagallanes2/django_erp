# django_erp/configuration/views.py
from django.shortcuts import render
from django.http import JsonResponse
from django.contrib.admin.views.decorators import staff_member_required


@staff_member_required
def switch_company(request):
    """Vista para cambiar de compañía"""
    company_id = request.GET.get('company_id')
    next_url = request.GET.get('next', '/admin/')
    
    if company_id:
        try:
            company = Company.objects.get(id=company_id, is_active=True)
            # Verificar que el usuario tiene acceso a esta compañía
            if request.user.is_superuser or company in request.user.companies.all():
                request.session['active_company_id'] = company.id
                messages.success(request, f'Compañía cambiada a: {company.name}')
            else:
                messages.error(request, 'No tienes acceso a esta compañía')
        except Company.DoesNotExist:
            messages.error(request, 'Compañía no encontrada')
    
    return redirect(next_url)