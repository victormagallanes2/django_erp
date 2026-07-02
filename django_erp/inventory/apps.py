from django.apps import AppConfig


class InventoryConfig(AppConfig):
    name = 'django_erp.inventory'

    def ready(self):
        # ✅ Importar signals solo cuando la app está lista
        from . import signals  # Esto debe existir