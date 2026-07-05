# invoicing/apps.py
from django.apps import AppConfig
from django.apps import apps


class InvoicingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'django_erp.invoicing'
    verbose_name = 'Facturación'
    
    def ready(self):
        # ✅ Solo importar signals si Sales está instalado
        if apps.is_installed('django_erp.sales'):
            try:
                import django_erp.invoicing.signals
                print("✅ Invoicing signals loaded (conected to Sales)")
            except Exception as e:
                print(f"⚠️ Error loading signals: {e}")
        else:
            print("ℹ️ Invoicing mode: independent (Sales not installed)")
