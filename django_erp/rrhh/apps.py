from django.apps import AppConfig


class RrhhConfig(AppConfig):
    name = 'django_erp.rrhh'
    default_auto_field = 'django.db.models.BigAutoField'

    def ready(self):
        # Importar señales cuando la app esté lista
        import django_erp.rrhh.signals
