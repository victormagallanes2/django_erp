# invoicing/apps.py
from django.apps import AppConfig


class InvoicingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'django_erp.invoicing'
    verbose_name = 'Facturación'
    
    def ready(self):
        # ✅ Importar signals para conectar
        import django_erp.invoicing.signals
        print("✅ Invoicing signals loaded and connected")
