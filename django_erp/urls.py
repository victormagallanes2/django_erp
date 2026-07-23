"""
URL configuration for django_erp project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include 
from django.conf import settings
from django.conf.urls.static import static
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse


# ✅ Health Check para verificar conexión real
@require_http_methods(["GET", "HEAD"])
def health_check(request):
    """Endpoint para verificar que el servidor está respondiendo"""
    return JsonResponse({'status': 'ok', 'timestamp': '2026-01-19'})

urlpatterns = [
    # ✅ Health Check (para detectar conexión real)
    path('admin/health-check/', health_check, name='health_check'),
    path('admin/sales/', include('django_erp.sales.urls')),
    path('admin/invoicing/', include('django_erp.invoicing.urls')),
    path('admin/purchasing/', include('django_erp.purchasing.urls')),
    path('admin/', admin.site.urls),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)