# django_erp/purchasing/apps.py
from django.apps import AppConfig


class PurchasingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'django_erp.purchasing'
    verbose_name = 'Compras'
    
    def ready(self):
        import django_erp.purchasing.signals
        print("✅ Purchasing signals loaded")
