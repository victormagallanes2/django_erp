# sales/module_info.py
MODULE_INFO = {
    'name': 'sales',
    'verbose_name': 'Ventas',
    'description': 'Gestión de ventas y clientes',
    'version': '1.0.0',
    'dependencies': ['warehouse'],
    'optional_dependencies': ['invoicing'],  # ← Invoicing es opcional
}