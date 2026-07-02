# sales/apps.py
from django.apps import AppConfig


class SalesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'django_erp.sales'
    verbose_name = 'Ventas'
    
    def ready(self):
        # ✅ Importar signals para conectar
        import django_erp.sales.signals
        print("✅ Sales signals loaded and connected")
