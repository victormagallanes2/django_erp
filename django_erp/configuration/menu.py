# django_erp/configuration/menu.py
"""
Configuración del menú del sidebar de Unfold.

Se importa desde `settings.py` en la sección UNFOLD.SIDEBAR.navigation.
"""


def get_menu_items(request):
    """
    Genera el menú según los permisos del usuario autenticado.
    
    Args:
        request: HttpRequest con `request.user` autenticado.
    
    Returns:
        list: Lista de dicts con la estructura de navegación de Unfold.
    """
    user = request.user
    
    if not user.is_authenticated:
        return []
    
    navigation = []
    
    # ============================================================
    # INVENTARIO
    # ============================================================
    if (user.has_perm('inventory.view_product') 
        or user.has_perm('inventory.view_movement') 
        or user.has_perm('inventory.view_inventory')):
        
        inventory_items = []
        
        if user.has_perm('inventory.view_inventory'):
            inventory_items.append({
                "title": "Inventarios",
                "icon": "storage",
                "link": "/admin/inventory/inventory/",
            })
        if user.has_perm('inventory.view_movement'):
            inventory_items.append({
                "title": "Movimientos",
                "icon": "swap_horiz",
                "link": "/admin/inventory/movement/",
            })
        if user.has_perm('inventory.view_product'):
            inventory_items.append({
                "title": "Productos",
                "icon": "inventory_2",
                "link": "/admin/inventory/product/",
            })
        if user.has_perm('inventory.view_deliverynote'):
            inventory_items.append({
                "title": "Notas de Entrega",
                "icon": "fact_check",
                "link": "/admin/inventory/deliverynote/",
            })
        if user.has_perm('inventory.view_receiptnote'):
            inventory_items.append({
                "title": "Notas de Recibo",
                "icon": "move_up",
                "link": "/admin/inventory/receiptnote/",
            })
        if user.has_perm('inventory.view_location'):
            inventory_items.append({
                "title": "Ubicaciones",
                "icon": "location_on",
                "link": "/admin/inventory/location/",
            })
        if user.has_perm('inventory.view_physicalcount'):
            inventory_items.append({
                "title": "Ajuste de inventario",
                "icon": "fact_check",
                "link": "/admin/inventory/physicalcount/",
            })
        
        if inventory_items:
            navigation.append({
                "title": "Inventario",
                "separator": True,
                "collapsible": True,
                "items": inventory_items,
            })
    
    # ============================================================
    # COMPRAS
    # ============================================================
    # if (user.has_perm('purchasing.view_supplier') 
    #     or user.has_perm('purchasing.view_purchaseorder')):
        
    #     purchasing_items = []
        
    #     if user.has_perm('purchasing.view_supplier'):
    #         purchasing_items.append({
    #             "title": "Proveedores",
    #             "icon": "business",
    #             "link": "/admin/purchasing/supplier/",
    #         })
    #     if user.has_perm('purchasing.view_purchaseorder'):
    #         purchasing_items.append({
    #             "title": "Órdenes de Compras",
    #             "icon": "shopping_cart",
    #             "link": "/admin/purchasing/purchaseorder/",
    #         })
    #     if user.has_perm('purchasing.view_purchaseinvoice'):
    #         purchasing_items.append({
    #             "title": "Facturas de Compra",
    #             "icon": "receipt",
    #             "link": "/admin/purchasing/purchaseinvoice/",
    #         })
        
    #     if purchasing_items:
    #         navigation.append({
    #             "title": "Compras",
    #             "separator": True,
    #             "collapsible": True,
    #             "items": purchasing_items,
    #         })
    
    # ============================================================
    # VENTAS
    # ============================================================
    if (user.has_perm('sales.view_saleorder') 
        or user.has_perm('sales.view_customer')):
        
        sales_items = []
        
        if user.has_perm('sales.view_customer'):
            sales_items.append({
                "title": "Clientes",
                "icon": "person",
                "link": "/admin/sales/customer/",
            })
        # if user.has_perm('sales.view_saleorder'):
        #     sales_items.append({
        #         "title": "Órdenes de Ventas",
        #         "icon": "receipt_long",
        #         "link": "/admin/sales/saleorder/",
        #     })
        if user.has_perm('sales.view_saleinvoice'):
            sales_items.append({
                "title": "Facturas de Ventas",
                "icon": "fact_check",
                "link": "/admin/sales/saleinvoice/",
            })
        if user.has_perm('sales.add_saleinvoice'):
            sales_items.append({
                "title": "Punto de Venta",
                "icon": "point_of_sale",
                "link": "/admin/sales/saleinvoice/pos/",
            })
        if user.has_perm('sales.view_cashregister'):
            sales_items.append({
                "title": "Cajas",
                "icon": "payments",
                "link": "/admin/sales/cashregister/",
            })
        if user.has_perm('sales.can_view_reports'):
            sales_items.append({
                "title": "Reporte de Ventas",
                "icon": "assessment",
                "link": "/admin/sales/saleinvoice/sales-report/",
            })
        
        if sales_items:
            navigation.append({
                "title": "Ventas",
                "separator": True,
                "collapsible": True,
                "items": sales_items,
            })
    
    # ============================================================
    # CONTABILIDAD
    # ============================================================
    if (user.has_perm('accounting.view_tax')
        or user.has_perm('accounting.view_taxrate')
        or user.has_perm('accounting.view_exchangerate')):
        
        accounting_items = []
        
        if user.has_perm('accounting.view_tax'):
            accounting_items.append({
                "title": "Tipos de Impuestos",
                "icon": "receipt",
                "link": "/admin/accounting/tax/",
            })
        if user.has_perm('accounting.view_taxrate'):
            accounting_items.append({
                "title": "Tasas de Impuesto",
                "icon": "percent",
                "link": "/admin/accounting/taxrate/",
            })
        if user.has_perm('accounting.view_exchangerate'):
            accounting_items.append({
                "title": "Tasas de Cambio",
                "icon": "swap_horiz",
                "link": "/admin/accounting/exchangerate/",
            })
        
        if accounting_items:
            navigation.append({
                "title": "Contabilidad",
                "separator": True,
                "collapsible": True,
                "items": accounting_items,
            })
    
    # ============================================================
    # RECURSOS HUMANOS
    # ============================================================
    if (user.has_perm('rrhh.view_employee') 
        or user.has_perm('rrhh.view_commission')):
        
        rrhh_items = []
        
        if user.has_perm('rrhh.view_employee'):
            rrhh_items.append({
                "title": "Empleados",
                "icon": "badge",
                "link": "/admin/rrhh/employee/",
            })
        if user.has_perm('rrhh.view_commission'):
            rrhh_items.append({
                "title": "Comisiones",
                "icon": "payments",
                "link": "/admin/rrhh/commission/",
            })
        
        if rrhh_items:
            navigation.append({
                "title": "Recursos Humanos",
                "separator": True,
                "collapsible": True,
                "items": rrhh_items,
            })
    
    # ============================================================
    # CONFIGURACIÓN (solo superuser)
    # ============================================================
    if user.is_superuser:
        navigation.append({
            "title": "Configuración",
            "separator": True,
            "collapsible": True,
            "items": [
                {
                    "title": "Empresa",
                    "icon": "business",
                    "link": "/admin/configuration/company/",
                },
                {
                    "title": "Usuarios",
                    "icon": "people",
                    "link": "/admin/users/user/",
                },
                {
                    "title": "Grupos",
                    "icon": "group",
                    "link": "/admin/auth/group/",
                },
                {
                    "title": "Monedas",
                    "icon": "attach_money",
                    "link": "/admin/configuration/currency/",
                },
                {
                    "title": "Métodos de Pago",
                    "icon": "payments",
                    "link": "/admin/configuration/paymentmethod/",
                },
                {
                    "title": "Cuentas Bancarias",
                    "icon": "account_balance",
                    "link": "/admin/configuration/companybankaccount/",
                },
                {
                    "title": "Respaldos",
                    "icon": "backup",
                    "link": "/admin/configuration/backup/",
                },
            ]
        })
    
    return navigation