# django_erp/configuration/views.py
from django.shortcuts import render
from django.http import JsonResponse
from django.contrib.admin.views.decorators import staff_member_required

@staff_member_required
def test_context(request):
    """Vista de prueba para verificar el context processor"""
    return render(request, 'admin/configuration/test_context.html')