# invoicing/module_info.py
MODULE_INFO = {
    'name': 'invoicing',
    'verbose_name': 'Facturación',
    'description': 'Gestión de facturación',
    'version': '1.0.0',
    'dependencies': ['sales', 'warehouse'],  # ← Requiere Sales
}