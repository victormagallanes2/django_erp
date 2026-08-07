# configuration/data/load_data.py
"""
Script para cargar TODOS los datos iniciales de una sola vez
Uso: 
    python -m django_erp.configuration.data.load_data
"""

import os
import sys
import django
from decimal import Decimal
from datetime import datetime, date, timedelta
import traceback

# ✅ CONFIGURAR DJANGO PRIMERO
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'django_erp.settings')
django.setup()

# ✅ AHORA SÍ, importar el resto
import json
from django.contrib.auth.models import Group, Permission
from django.contrib.auth import get_user_model
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.db import connections

# ✅ Importar modelos
from django_erp.configuration.models import (
    Currency, ExchangeRate, PaymentMethod, Company, CompanyBankAccount
)
from django_erp.users.models import User
from django_erp.warehouse.models import Product, Location
from django_erp.inventory.models import Inventory, ValuationMethod
from django_erp.purchasing.models import Supplier
from django_erp.sales.models import Customer

User = get_user_model()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, 'data')


# ============================================================
# FUNCIÓN: Crear Compañías
# ============================================================

def get_or_create_companies():
    """
    Crear compañías para diferentes países/regiones
    Retorna: dict con todas las compañías creadas
    """
    print("=" * 70)
    print("🏢 CREANDO COMPAÑÍAS")
    print("=" * 70)
    
    companies = {}
    
    # ✅ 1. Compañía Principal (Venezuela)
    company_ve, created = Company.objects.get_or_create(
        code='MAIN',
        defaults={
            'name': 'Mi Empresa Principal C.A.',
            'rif': 'J-12345678-9',
            'trade_name': 'Mi Empresa C.A.',
            'address': 'Av. Principal #123, Caracas, Venezuela',
            'phone': '+58-212-555-0000',
            'email': 'contacto@miempresa.com',
            'website': 'https://www.miempresa.com',
            'tax_rate': 16.00,
            'invoice_prefix': 'FAC',
            'is_main': True,
            'is_active': True,
        }
    )
    companies['VE'] = company_ve
    print(f"   ✅ {company_ve.code} - {company_ve.name} (Venezuela) {'(Principal)' if company_ve.is_main else ''}")
    
    # ✅ 2. Sucursal Colombia
    company_co, created = Company.objects.get_or_create(
        code='COL',
        defaults={
            'name': 'Mi Empresa Colombia S.A.S.',
            'rif': '900-123456-7',
            'trade_name': 'Mi Empresa Colombia',
            'address': 'Calle 123 #45-67, Bogotá, Colombia',
            'phone': '+57-1-555-0000',
            'email': 'colombia@miempresa.com',
            'website': 'https://www.miempresa.com/colombia',
            'tax_rate': 19.00,
            'invoice_prefix': 'FAC-COL',
            'is_main': False,
            'is_active': True,
            'parent': company_ve,
        }
    )
    companies['CO'] = company_co
    print(f"   ✅ {company_co.code} - {company_co.name} (Colombia)")
    
    # ✅ 3. Sucursal México
    company_mx, created = Company.objects.get_or_create(
        code='MX',
        defaults={
            'name': 'Mi Empresa México S.A. de C.V.',
            'rif': 'MX-123456789',
            'trade_name': 'Mi Empresa México',
            'address': 'Av. Reforma #456, Ciudad de México, México',
            'phone': '+52-55-5555-0000',
            'email': 'mexico@miempresa.com',
            'website': 'https://www.miempresa.com/mexico',
            'tax_rate': 16.00,
            'invoice_prefix': 'FAC-MX',
            'is_main': False,
            'is_active': True,
            'parent': company_ve,
        }
    )
    companies['MX'] = company_mx
    print(f"   ✅ {company_mx.code} - {company_mx.name} (México)")
    
    # ✅ 4. Sucursal Europa (España)
    company_es, created = Company.objects.get_or_create(
        code='ES',
        defaults={
            'name': 'Mi Empresa España S.L.',
            'rif': 'ES-987654321',
            'trade_name': 'Mi Empresa España',
            'address': 'Calle Mayor #789, Madrid, España',
            'phone': '+34-91-555-0000',
            'email': 'espana@miempresa.com',
            'website': 'https://www.miempresa.com/espana',
            'tax_rate': 21.00,
            'invoice_prefix': 'FAC-ES',
            'is_main': False,
            'is_active': True,
            'parent': company_ve,
        }
    )
    companies['ES'] = company_es
    print(f"   ✅ {company_es.code} - {company_es.name} (España)")
    
    print("=" * 70)
    return companies


# ============================================================
# FUNCIÓN: Cargar Monedas GLOBALES
# ============================================================

def load_global_currencies():
    """Cargar monedas GLOBALES (compartidas por todas las compañías)"""
    print("\n" + "=" * 70)
    print("💱 CARGANDO MONEDAS GLOBALES")
    print("=" * 70)
    
    # ✅ Definir monedas globales
    currencies_data = [
        {'code': 'USD', 'name': 'Dólar Americano', 'symbol': '$', 'is_base': True},
        {'code': 'BS', 'name': 'Bolívar', 'symbol': 'Bs.', 'is_base': False},
        {'code': 'EUR', 'name': 'Euro', 'symbol': '€', 'is_base': False},
        {'code': 'COP', 'name': 'Peso Colombiano', 'symbol': '$', 'is_base': False},
        {'code': 'MXN', 'name': 'Peso Mexicano', 'symbol': '$', 'is_base': False},
        {'code': 'GBP', 'name': 'Libra Esterlina', 'symbol': '£', 'is_base': False},
    ]
    
    count = 0
    for curr_data in currencies_data:
        currency, created = Currency.objects.get_or_create(
            code=curr_data['code'],
            defaults={
                'name': curr_data['name'],
                'symbol': curr_data['symbol'],
                'decimal_places': 2,
                'is_base': curr_data['is_base'],
                'is_active': True,
            }
        )
        if created:
            count += 1
            base_mark = " (BASE)" if currency.is_base else ""
            print(f"   ✅ Creada: {currency.code} - {currency.name}{base_mark}")
        else:
            print(f"   ℹ️ Ya existe: {currency.code} - {currency.name}")
    
    print(f"✅ Monedas globales cargadas: {count} nuevas")
    return count


# ============================================================
# FUNCIÓN: Cargar Tasas de Cambio por Compañía CON HISTORIAL
# ============================================================

def load_exchange_rates(company):
    """Cargar tasas de cambio históricas para una compañía específica"""
    print(f"\n   📥 Cargando tasas de cambio para {company.code}...")
    
    try:
        # ✅ Obtener moneda base global
        base_currency = Currency.get_base()
        if not base_currency:
            print(f"   ⚠️ No se encontró moneda base global para {company.code}")
            return 0
        
        # ✅ Obtener monedas que no son base
        other_currencies = Currency.objects.exclude(code=base_currency.code)
        
        count = 0
        today = date.today()
        
        for currency in other_currencies:
            # ✅ Definir tasas históricas para tener historial desde el inicio
            historical_rates = []
            
            if company.code == 'VE' and currency.code == 'BS':
                # Simular tasas históricas para Venezuela
                historical_rates = [
                    {'date': today - timedelta(days=30), 'rate': Decimal('38.00')},
                    {'date': today - timedelta(days=15), 'rate': Decimal('39.00')},
                    {'date': today - timedelta(days=7), 'rate': Decimal('39.50')},
                    {'date': today, 'rate': Decimal('40.00')},
                ]
            elif company.code == 'CO' and currency.code == 'COP':
                historical_rates = [
                    {'date': today - timedelta(days=30), 'rate': Decimal('3800.00')},
                    {'date': today - timedelta(days=15), 'rate': Decimal('3900.00')},
                    {'date': today - timedelta(days=7), 'rate': Decimal('3950.00')},
                    {'date': today, 'rate': Decimal('4000.00')},
                ]
            elif company.code == 'MX' and currency.code == 'MXN':
                historical_rates = [
                    {'date': today - timedelta(days=30), 'rate': Decimal('17.00')},
                    {'date': today - timedelta(days=15), 'rate': Decimal('17.50')},
                    {'date': today - timedelta(days=7), 'rate': Decimal('17.80')},
                    {'date': today, 'rate': Decimal('18.00')},
                ]
            elif company.code == 'ES' and currency.code == 'USD':
                historical_rates = [
                    {'date': today - timedelta(days=30), 'rate': Decimal('1.05')},
                    {'date': today - timedelta(days=15), 'rate': Decimal('1.08')},
                    {'date': today - timedelta(days=7), 'rate': Decimal('1.09')},
                    {'date': today, 'rate': Decimal('1.10')},
                ]
            elif company.code == 'ES' and currency.code == 'GBP':
                historical_rates = [
                    {'date': today - timedelta(days=30), 'rate': Decimal('0.80')},
                    {'date': today - timedelta(days=15), 'rate': Decimal('0.83')},
                    {'date': today - timedelta(days=7), 'rate': Decimal('0.84')},
                    {'date': today, 'rate': Decimal('0.85')},
                ]
            
            # ✅ Si hay tasas históricas definidas, crearlas
            if historical_rates:
                for hist in historical_rates:
                    rate, created = ExchangeRate.objects.get_or_create(
                        from_currency=base_currency,
                        to_currency=currency,
                        company=company,
                        effective_date=hist['date'],
                        defaults={
                            'rate': hist['rate'],
                            'source': 'Sistema - Histórico',
                            'note': f'Tasa histórica cargada para {hist["date"].strftime("%Y-%m-%d")}'
                        }
                    )
                    if created:
                        count += 1
                        print(f"      ✅ Creada: 1 {base_currency.code} = {hist['rate']} {currency.code} (vigente desde {hist['date'].strftime('%Y-%m-%d')})")
                    else:
                        print(f"      ℹ️ Ya existe: 1 {base_currency.code} = {rate.rate} {currency.code} (vigente desde {rate.effective_date.strftime('%Y-%m-%d')})")
            else:
                # ✅ Si no hay históricas, crear solo la tasa actual
                rate_value = Decimal('1.00')
                
                if company.code == 'VE' and currency.code == 'BS':
                    rate_value = Decimal('40.00')
                elif company.code == 'CO' and currency.code == 'COP':
                    rate_value = Decimal('4000.00')
                elif company.code == 'MX' and currency.code == 'MXN':
                    rate_value = Decimal('18.00')
                elif company.code == 'ES':
                    if currency.code == 'USD':
                        rate_value = Decimal('1.10')
                    elif currency.code == 'GBP':
                        rate_value = Decimal('0.85')
                
                rate, created = ExchangeRate.objects.get_or_create(
                    from_currency=base_currency,
                    to_currency=currency,
                    company=company,
                    effective_date=today,
                    defaults={
                        'rate': rate_value,
                        'source': 'Sistema',
                        'note': 'Tasa inicial del sistema'
                    }
                )
                if created:
                    count += 1
                    print(f"      ✅ Creada: 1 {base_currency.code} = {rate_value} {currency.code} (vigente desde hoy)")
                else:
                    print(f"      ℹ️ Ya existe: 1 {base_currency.code} = {rate.rate} {currency.code}")
        
        print(f"   ✅ Tasas cargadas: {count} nuevas para {company.code}")
        return count
        
    except Exception as e:
        print(f"   ❌ Error cargando tasas para {company.code}: {str(e)}")
        traceback.print_exc()
        return 0


# ============================================================
# FUNCIÓN: Cargar Métodos de Pago por Compañía
# ============================================================

def load_payment_methods(company):
    """Cargar métodos de pago para una compañía específica"""
    print(f"\n   📥 Cargando métodos de pago para {company.code}...")
    
    try:
        # ✅ Obtener moneda base global
        base_currency = Currency.get_base()
        if not base_currency:
            print(f"   ⚠️ No se encontró moneda base global para {company.code}")
            return 0
    except Exception as e:
        print(f"   ⚠️ Error obteniendo moneda base: {e}")
        return 0
    
    # ✅ Métodos de pago por defecto
    payment_methods = [
        {'code': 'CASH', 'name': 'Efectivo', 'requires_approval': False},
        {'code': 'BANK_TRANSFER', 'name': 'Transferencia Bancaria', 'requires_approval': True},
        {'code': 'CHECK', 'name': 'Cheque', 'requires_approval': True},
        {'code': 'CREDIT_CARD', 'name': 'Tarjeta de Crédito', 'requires_approval': False},
        {'code': 'MOBILE_PAYMENT', 'name': 'Pago Móvil', 'requires_approval': False},
    ]
    
    count = 0
    for method_data in payment_methods:
        try:
            method, created = PaymentMethod.objects.get_or_create(
                code=method_data['code'],
                company=company,
                defaults={
                    'name': method_data['name'],
                    'description': f"Método de pago: {method_data['name']}",
                    'requires_approval': method_data['requires_approval'],
                    'requires_company_bank': method_data['code'] in ['BANK_TRANSFER', 'CHECK'],
                    'requires_reference': method_data['code'] in ['BANK_TRANSFER', 'CHECK', 'CREDIT_CARD'],
                    'default_currency': base_currency,
                    'is_active': True,
                }
            )
            
            if created:
                count += 1
                print(f"      ✅ Creado: {method.name} ({method.code}) para {company.code}")
            else:
                print(f"      ℹ️ Ya existe: {method.name} ({method.code}) para {company.code}")
        except Exception as e:
            print(f"      ❌ Error creando método {method_data['code']}: {e}")
    
    print(f"   ✅ Métodos de pago cargados: {count} nuevos para {company.code}")
    return count


# ============================================================
# FUNCIÓN: Cargar Cuentas Bancarias por Compañía
# ============================================================

def load_company_bank_accounts(company):
    """Crear cuentas bancarias para una compañía"""
    print(f"\n   📥 Creando cuentas bancarias para {company.code}...")
    
    try:
        base_currency = Currency.get_base()
        if not base_currency:
            print(f"   ⚠️ No se encontró moneda base global para {company.code}")
            return 0
        
        # ✅ Cuentas bancarias según el país
        accounts = []
        
        if company.code == 'VE':
            accounts.append({
                'bank_name': 'Banco Nacional de Venezuela',
                'account_number': f'0102-{company.code}-0001',
                'account_holder': company.name,
                'currency': base_currency,
                'is_default': True,
            })
            accounts.append({
                'bank_name': 'Banco Internacional',
                'account_number': f'0105-{company.code}-0002',
                'account_holder': company.name,
                'currency': base_currency,
                'is_default': False,
            })
        elif company.code == 'CO':
            accounts.append({
                'bank_name': 'Banco de Colombia',
                'account_number': f'0102-{company.code}-0001',
                'account_holder': company.name,
                'currency': base_currency,
                'is_default': True,
            })
        elif company.code == 'MX':
            accounts.append({
                'bank_name': 'Banco de México',
                'account_number': f'0102-{company.code}-0001',
                'account_holder': company.name,
                'currency': base_currency,
                'is_default': True,
            })
        elif company.code == 'ES':
            accounts.append({
                'bank_name': 'Banco de España',
                'account_number': f'0102-{company.code}-0001',
                'account_holder': company.name,
                'currency': base_currency,
                'is_default': True,
            })
        
        count = 0
        for acc_data in accounts:
            account, created = CompanyBankAccount.objects.get_or_create(
                bank_name=acc_data['bank_name'],
                account_number=acc_data['account_number'],
                company=company,
                defaults={
                    'account_holder': acc_data['account_holder'],
                    'account_type': 'CHECKING',
                    'currency': acc_data['currency'],
                    'is_default': acc_data['is_default'],
                    'is_active': True,
                }
            )
            if created:
                count += 1
                print(f"      ✅ Cuenta creada: {account.bank_name} - {account.account_number}")
            else:
                print(f"      ℹ️ Cuenta ya existe: {account.bank_name} - {account.account_number}")
        
        print(f"   ✅ Cuentas bancarias: {count} nuevas para {company.code}")
        return count
        
    except Exception as e:
        print(f"   ❌ Error cargando cuentas para {company.code}: {str(e)}")
        traceback.print_exc()
        return 0


# ============================================================
# FUNCIÓN: Cargar Datos de Demostración por Compañía
# ============================================================

def load_demo_data(company):
    """Cargar datos de demostración para una compañía específica"""
    print(f"\n   📥 Cargando datos demo para {company.code}...")
    
    try:
        base_currency = Currency.get_base()
        if not base_currency:
            print(f"   ⚠️ No se encontró moneda base global")
            return False
        
        # ✅ 1. Crear ubicaciones
        locations = []
        for loc_data in [
            {'code': f'ALM-{company.code}-01', 'name': f'Almacén Principal {company.code}'},
            {'code': f'ALM-{company.code}-02', 'name': f'Almacén Secundario {company.code}'},
        ]:
            loc, created = Location.objects.get_or_create(
                code=loc_data['code'],
                company=company,
                defaults={
                    'name': loc_data['name'],
                    'is_active': True,
                }
            )
            locations.append(loc)
            if created:
                print(f"      ✅ Ubicación: {loc.code}")
        
        # ✅ 2. Crear productos
        products = []
        # Precios en moneda base de la compañía
        base_price = Decimal('850.00')
        if company.code == 'ES':
            base_price = Decimal('750.00')  # Euros
        
        product_data = [
            {'code': f'PROD-{company.code}-001', 'name': f'Laptop Pro {company.code}', 'price': base_price, 'is_service': False},
            {'code': f'PROD-{company.code}-002', 'name': f'Mouse Inalámbrico {company.code}', 'price': base_price * Decimal('0.03'), 'is_service': False},
            {'code': f'PROD-{company.code}-003', 'name': f'Monitor 24" {company.code}', 'price': base_price * Decimal('0.40'), 'is_service': False},
            {'code': f'SERV-{company.code}-001', 'name': f'Consultoría TI {company.code}', 'price': base_price * Decimal('0.12'), 'is_service': True},
        ]
        
        for prod_data in product_data:
            prod, created = Product.objects.get_or_create(
                code=prod_data['code'],
                company=company,
                defaults={
                    'name': prod_data['name'],
                    'price': prod_data['price'],
                    'is_service': prod_data['is_service'],
                    'is_active': True,
                    'unit': 'UNIT',
                }
            )
            products.append(prod)
            if created:
                print(f"      ✅ Producto: {prod.code} - {prod.name}")
        
        # ✅ 3. Crear inventarios (solo productos físicos)
        for prod in products:
            if not prod.is_service and locations:
                inventory, created = Inventory.objects.get_or_create(
                    product=prod,
                    location=locations[0],
                    company=company,
                    defaults={
                        'quantity': 10,
                        'average_cost': prod.price,
                        'total_value': prod.price * 10,
                    }
                )
                if created:
                    print(f"      ✅ Inventario: {prod.name} = 10 unidades")
        
        # ✅ 4. Crear métodos de valoración
        for prod in products:
            if not prod.is_service:
                val_method, created = ValuationMethod.objects.get_or_create(
                    product=prod,
                    company=company,
                    defaults={
                        'method': 'AVERAGE',
                        'standard_cost': prod.price,
                    }
                )
                if created:
                    print(f"      ✅ Método de valoración: {prod.name}")
        
        # ✅ 5. Crear proveedores
        for sup_data in [
            {'name': f'Proveedor Local {company.code}', 'tax_id': f'LOCAL-{company.code}-001', 'email': f'local@{company.code}.com'},
            {'name': f'Proveedor Internacional {company.code}', 'tax_id': f'INTL-{company.code}-001', 'email': f'intl@{company.code}.com'},
        ]:
            sup, created = Supplier.objects.get_or_create(
                tax_id=sup_data['tax_id'],
                company=company,
                defaults={
                    'name': sup_data['name'],
                    'email': sup_data['email'],
                    'is_active': True,
                }
            )
            if created:
                print(f"      ✅ Proveedor: {sup.name}")
        
        # ✅ 6. Crear clientes
        for cust_data in [
            {'name': f'Cliente VIP {company.code}', 'tax_id': f'VIP-{company.code}-001', 'email': f'vip@{company.code}.com'},
            {'name': f'Cliente Regular {company.code}', 'tax_id': f'REG-{company.code}-001', 'email': f'reg@{company.code}.com'},
        ]:
            cust, created = Customer.objects.get_or_create(
                tax_id=cust_data['tax_id'],
                company=company,
                defaults={
                    'name': cust_data['name'],
                    'email': cust_data['email'],
                    'is_active': True,
                }
            )
            if created:
                print(f"      ✅ Cliente: {cust.name}")
        
        print(f"   ✅ Datos demo completados para {company.code}")
        return True
        
    except Exception as e:
        print(f"   ❌ Error en {company.code}: {str(e)}")
        traceback.print_exc()
        return False


# ============================================================
# FUNCIÓN: Cargar Grupos (Globales)
# ============================================================

def load_groups():
    """Cargar grupos desde JSON (globales, sin compañía)"""
    print("\n" + "=" * 70)
    print("👥 CARGANDO GRUPOS GLOBALES")
    print("=" * 70)
    
    file_path = os.path.join(DATA_DIR, 'groups.json')
    
    if not os.path.exists(file_path):
        print("   ⚠️ No se encontró groups.json")
        return 0
    
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    count = 0
    for item in data:
        fields = item['fields']
        group, created = Group.objects.get_or_create(
            name=fields['name'],
            defaults={}
        )
        if created:
            count += 1
            print(f"   ✅ Creado: {group.name}")
        
        if fields.get('permissions'):
            permissions = Permission.objects.filter(pk__in=fields['permissions'])
            group.permissions.set(permissions)
    
    print(f"✅ Grupos cargados: {count} nuevos")
    return count


# ============================================================
# FUNCIÓN: Cargar Usuarios
# ============================================================

def load_users(companies):
    """Cargar usuarios y asignar compañías según el país"""
    print("\n" + "=" * 70)
    print("👤 CARGANDO USUARIOS")
    print("=" * 70)
    
    count = 0
    
    # ✅ Usuario Admin - Acceso a TODAS las compañías
    admin, created = User.objects.get_or_create(
        username='admin',
        defaults={
            'email': 'admin@miempresa.com',
            'first_name': 'Administrador',
            'last_name': 'Global',
            'is_superuser': True,
            'is_staff': True,
            'is_active': True,
        }
    )
    if created:
        admin.set_password('admin123')
        admin.save()
        count += 1
        print(f"   ✅ Creado: admin (Superusuario)")
    else:
        print(f"   ℹ️ Usuario admin ya existe")
    
    # ✅ Asignar TODAS las compañías al admin
    for comp in companies.values():
        admin.companies.add(comp)
    print(f"   ✅ Admin tiene acceso a: {', '.join([c.code for c in companies.values()])}")
    
    # ✅ Usuarios por compañía
    user_data = []
    for code in companies.keys():
        user_data.extend([
            {'username': f'gerente_{code}', 'email': f'gerente@{code.lower()}.com', 'company': code, 'groups': ['Administradores']},
            {'username': f'ventas_{code}', 'email': f'ventas@{code.lower()}.com', 'company': code, 'groups': ['Ventas']},
            {'username': f'almacen_{code}', 'email': f'almacen@{code.lower()}.com', 'company': code, 'groups': ['Almacen']},
        ])
    
    for data_item in user_data:
        company = companies.get(data_item['company'])
        if not company:
            print(f"   ⚠️ Compañía {data_item['company']} no encontrada")
            continue
        
        user, created = User.objects.get_or_create(
            username=data_item['username'],
            defaults={
                'email': data_item['email'],
                'first_name': data_item['username'].capitalize(),
                'last_name': data_item['company'],
                'is_superuser': False,
                'is_staff': True,
                'is_active': True,
            }
        )
        
        if created:
            user.set_password('123456')
            user.save()
            count += 1
            print(f"   ✅ Creado: {user.username} para {company.code}")
        else:
            print(f"   ℹ️ Usuario {user.username} ya existe")
        
        # ✅ Asignar compañía
        user.companies.add(company)
        
        # ✅ Asignar grupos
        for group_name in data_item.get('groups', []):
            try:
                group = Group.objects.get(name=group_name)
                user.groups.add(group)
                print(f"   ✅ Grupo '{group_name}' asignado a {user.username}")
            except Group.DoesNotExist:
                print(f"   ⚠️ Grupo '{group_name}' no encontrado para {user.username}")
        
        user.save()
    
    print(f"✅ Usuarios cargados: {count} nuevos")
    return count


# ============================================================
# FUNCIÓN PRINCIPAL: Cargar TODO
# ============================================================

def load_all():
    """Cargar TODOS los datos en orden correcto"""
    print("=" * 70)
    print("📥 CARGANDO TODOS LOS DATOS INICIALES")
    print("=" * 70)
    
    if not os.path.exists(DATA_DIR):
        print("⚠️ No existe el directorio data/")
        return
    
    # ✅ Verificar conexión
    try:
        connections['default'].ensure_connection()
        print("✅ Base de datos conectada")
    except Exception as e:
        print(f"❌ Error conectando: {e}")
        return
    
    try:
        with transaction.atomic():
            # ✅ PASO 1: Crear monedas globales PRIMERO
            load_global_currencies()
            
            # ✅ PASO 2: Crear compañías
            companies = get_or_create_companies()
            
            # ✅ PASO 3: Cargar datos globales
            load_groups()
            
            # ✅ PASO 4: Cargar datos por compañía
            print("\n" + "=" * 70)
            print("📦 CARGANDO DATOS POR COMPAÑÍA")
            print("=" * 70)
            
            for code, company in companies.items():
                print("\n" + "-" * 70)
                print(f"🏢 PROCESANDO: {company.code} - {company.name}")
                print("-" * 70)
                
                # ✅ Asignar moneda por defecto a la compañía
                if not company.default_currency:
                    base = Currency.get_base()
                    if base:
                        company.default_currency = base
                        company.save()
                        print(f"   ✅ Moneda por defecto asignada: {base.code}")
                
                # 1. Tasas de cambio (con historial)
                load_exchange_rates(company)
                
                # 2. Métodos de pago
                load_payment_methods(company)
                
                # 3. Cuentas bancarias
                load_company_bank_accounts(company)
                
                # 4. Datos de demostración
                load_demo_data(company)
            
            # ✅ PASO 5: Cargar usuarios
            load_users(companies)
        
        # ✅ VERIFICAR RESULTADOS
        print("\n" + "=" * 70)
        print("🔍 VERIFICANDO DATOS CARGADOS")
        print("=" * 70)
        
        # ✅ Monedas globales
        print(f"\n💱 MONEDAS GLOBALES: {Currency.objects.count()}")
        for currency in Currency.objects.all():
            base_mark = " (BASE)" if currency.is_base else ""
            print(f"   • {currency.code} - {currency.name}{base_mark}")
        
        # ✅ Compañías
        print(f"\n🏢 COMPAÑÍAS: {Company.objects.count()}")
        for comp in Company.objects.all():
            parent = f" (Padre: {comp.parent.code})" if comp.parent else " (Principal)"
            default_curr = comp.default_currency.code if comp.default_currency else "Sin moneda"
            print(f"   • {comp.code} - {comp.name}{parent} - Moneda: {default_curr}")
        
        # ✅ Tasas de cambio por compañía
        print(f"\n💰 TASAS DE CAMBIO POR COMPAÑÍA (con historial):")
        for comp in Company.objects.all():
            rates = ExchangeRate.objects.filter(company=comp)
            if rates.exists():
                print(f"   • {comp.code}: {rates.count()} tasas en total")
                # Mostrar solo las últimas 3
                last_rates = rates.order_by('-effective_date')[:3]
                for rate in last_rates:
                    print(f"      - {rate.effective_date.strftime('%Y-%m-%d')}: 1 {rate.from_currency.code} = {rate.rate} {rate.to_currency.code}")
                if rates.count() > 3:
                    print(f"      ... y {rates.count() - 3} más")
        
        # ✅ Métodos de pago
        print(f"\n💳 MÉTODOS DE PAGO POR COMPAÑÍA:")
        for comp in Company.objects.all():
            methods = PaymentMethod.objects.filter(company=comp)
            if methods.exists():
                print(f"   • {comp.code}: {', '.join([m.code for m in methods])}")
        
        # ✅ Usuarios
        print(f"\n👤 USUARIOS:")
        for user in User.objects.all():
            companies_list = user.companies.all()
            company_codes = [c.code for c in companies_list]
            print(f"   • {user.username} → {', '.join(company_codes) if company_codes else 'Sin compañía'}")
            if user.is_superuser:
                print(f"      (Superusuario)")
        
        # ✅ Productos por compañía
        print(f"\n📦 PRODUCTOS:")
        for comp in Company.objects.all():
            products = Product.objects.filter(company=comp)
            print(f"   • {comp.code}: {products.count()} productos")
        
        # ✅ Clientes por compañía
        print(f"\n👤 CLIENTES:")
        for comp in Company.objects.all():
            customers = Customer.objects.filter(company=comp)
            print(f"   • {comp.code}: {customers.count()} clientes")
        
        # ✅ Proveedores por compañía
        print(f"\n🤝 PROVEEDORES:")
        for comp in Company.objects.all():
            suppliers = Supplier.objects.filter(company=comp)
            print(f"   • {comp.code}: {suppliers.count()} proveedores")
        
        print("\n" + "=" * 70)
        print("✅ CARGA COMPLETADA EXITOSAMENTE")
        print("=" * 70)
        print("\n💡 INSTRUCCIONES:")
        print("   1. Ve al admin: http://127.0.0.1:8000/admin/")
        print("   2. Inicia sesión con:")
        print("      - Usuario: admin")
        print("      - Contraseña: admin123")
        print("   3. Busca el selector de compañías en la esquina superior derecha")
        print("   4. Cambia entre compañías y verás los datos específicos de cada país")
        print("\n🌍 COMPAÑÍAS DISPONIBLES:")
        for code, comp in companies.items():
            default_curr = comp.default_currency.code if comp.default_currency else "Sin moneda"
            rates_count = ExchangeRate.objects.filter(company=comp).count()
            print(f"   • {code} - {comp.name} (IVA: {comp.tax_rate}%, Moneda: {default_curr}, Tasas: {rates_count})")


if __name__ == '__main__':
    try:
        load_all()
    except Exception as e:
        print(f"\n❌ ERROR FATAL: {str(e)}")
        traceback.print_exc()
        sys.exit(1)