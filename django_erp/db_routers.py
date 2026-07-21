# django_erp/db_routers.py
"""
Router de base de datos para manejar la sincronización offline.
Decide qué base de datos usar según la conexión a internet y el modelo.
"""


class OfflineRouter:
    """
    Router que decide qué base de datos usar según:
    1. Si hay internet
    2. El tipo de operación (lectura/escritura)
    3. El modelo que se está usando
    """
    
    # ✅ Modelos que SIEMPRE van a PostgreSQL (SOLO LECTURA/ESCRITURA)
    # Estos modelos NO se sincronizan a SQLite por seguridad
    MASTER_MODELS = [
        'users.user',
        'auth.group',
        'auth.permission',
        'contenttypes.contenttype',
        'admin.logentry',
        'sessions.session',
    ]
    
    # ✅ Modelos que PUEDEN ir a SQLite (offline)
    # Estos modelos se sincronizan a SQLite para trabajar sin internet
    OFFLINE_MODELS = [
        # ✅ Configuración (necesario para facturar offline)
        'configuration.company',
        'configuration.currency',
        'configuration.exchangerate',
        
        # ✅ Warehouse (productos y ubicaciones para facturar)
        'warehouse.product',
        'warehouse.location',
        
        # ✅ Sales (clientes y órdenes de venta)
        'sales.customer',
        'sales.saleorder',
        'sales.saleline',
        
        # ✅ Invoicing (facturas y líneas)
        'invoicing.invoice',
        'invoicing.invoiceline',
        
        # ✅ Inventory (para consultas offline)
        'inventory.inventory',
        'inventory.physicalcount',
        'inventory.valuationmethod',
    ]
    
    # ================================================================
    # MÉTODOS PARA DECIDIR DÓNDE SE CREAN LAS TABLAS
    # ================================================================
    
    def allow_migrate(self, db, app_label, model_name=None, **hints):
        """
        ¿Dónde crear las tablas?
        Este método decide en qué base de datos se crean las tablas.
        """
        
        # ✅ Configuración → AMBAS bases de datos
        # Necesario para facturar offline (empresa, monedas, tasas)
        if app_label == 'configuration':
            return db in ['default', 'local']
        
        # ✅ Warehouse → AMBAS bases de datos
        # Necesario para productos y ubicaciones offline
        if app_label == 'warehouse':
            return db in ['default', 'local']
        
        # ✅ Sales → AMBAS bases de datos
        # Necesario para clientes y órdenes de venta offline
        if app_label == 'sales':
            return db in ['default', 'local']
        
        # ✅ Invoicing → AMBAS bases de datos
        # Necesario para facturar offline
        if app_label == 'invoicing':
            return db in ['default', 'local']
        
        # ✅ Inventory → AMBAS bases de datos
        # Para consultas de stock offline
        if app_label == 'inventory':
            return db in ['default', 'local']
        
        # ✅ Usuarios y Auth → SOLO PostgreSQL (seguridad)
        if app_label in ['users', 'auth', 'admin', 'contenttypes', 'sessions']:
            return db == 'default'
        
        # ✅ Por defecto, solo PostgreSQL
        return db == 'default'
    
    # ================================================================
    # MÉTODOS PARA DECIDIR DÓNDE SE LEE
    # ================================================================
    
    def db_for_read(self, model, **hints):
        """
        ¿De qué base de datos leer?
        """
        
        # ✅ Modelos maestros → siempre PostgreSQL
        if self._is_master_model(model):
            return 'default'
        
        # ✅ Si hay internet → PostgreSQL
        if self._is_online():
            return 'default'
        
        # ✅ Si no hay internet → SQLite
        return 'local'
    
    # ================================================================
    # MÉTODOS PARA DECIDIR DÓNDE SE ESCRIBE
    # ================================================================
    
    def db_for_write(self, model, **hints):
        """
        ¿En qué base de datos escribir?
        """
        
        # ✅ Modelos maestros → siempre PostgreSQL
        if self._is_master_model(model):
            return 'default'
        
        # ✅ Si hay internet → PostgreSQL
        if self._is_online():
            return 'default'
        
        # ✅ Si no hay internet → SQLite
        return 'local'
    
    # ================================================================
    # MÉTODOS PARA RELACIONES ENTRE BASES DE DATOS
    # ================================================================
    
    def allow_relation(self, obj1, obj2, **hints):
        """
        ¿Permitir relaciones entre objetos de diferentes bases de datos?
        """
        
        # ✅ Si ambos están en la misma base de datos, permitir
        db1 = self._get_db_for_object(obj1)
        db2 = self._get_db_for_object(obj2)
        
        if db1 == db2:
            return True
        
        # ✅ Si uno es 'local' y otro 'default', permitir (se sincronizan)
        if (db1 == 'local' and db2 == 'default') or (db1 == 'default' and db2 == 'local'):
            return True
        
        return False
    
    # ================================================================
    # MÉTODOS AUXILIARES
    # ================================================================
    
    def _is_online(self):
        """
        Verificar si hay internet.
        Por ahora, asumimos que estamos online.
        Más adelante, esto se conectará con un sistema de detección.
        """
        return True
    
    def _is_master_model(self, model):
        """
        Verificar si es un modelo maestro (solo en PostgreSQL).
        """
        app_label = model._meta.app_label
        model_name = model._meta.model_name
        key = f"{app_label}.{model_name}"
        return key in self.MASTER_MODELS
    
    def _get_db_for_object(self, obj):
        """
        Obtener la base de datos de un objeto.
        """
        if hasattr(obj, '_state'):
            state = obj._state
            if hasattr(state, 'db'):
                return state.db
            elif hasattr(state, '__dict__'):
                return getattr(state, 'db', 'default')
        return 'default'