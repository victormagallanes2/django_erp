# django_erp/db_routers.py
"""
Router de base de datos para manejar la sincronización offline.
Decide qué base de datos usar según la conexión a internet y el modelo.
"""


class OfflineRouter:
    """
    Router para manejar dos bases de datos SQLite.
    En desarrollo, ambas bases son SQLite.
    """
    
    def allow_migrate(self, db, app_label, model_name=None, **hints):
        """
        ¿Dónde crear las tablas?
        """
        # ✅ TODAS las apps van a AMBAS bases de datos
        return db in ['default', 'local']
    
    def db_for_read(self, model, **hints):
        """
        ¿De qué base de datos leer?
        """
        # ✅ Por ahora, siempre leer de 'default'
        return 'default'
    
    def db_for_write(self, model, **hints):
        """
        ¿En qué base de datos escribir?
        """
        # ✅ Por ahora, siempre escribir en 'default'
        return 'default'
    
    def allow_relation(self, obj1, obj2, **hints):
        """Permitir relaciones entre objetos"""
        return True