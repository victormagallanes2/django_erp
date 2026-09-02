# configuration/data/load_data.py
import os
import sys
import json
from decimal import Decimal
from datetime import date, datetime
from django.db import transaction
from django.contrib.auth.hashers import make_password

# Configuración de Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'django_erp.settings')
import django
django.setup()

# Importar modelos directamente
from django.contrib.auth.models import Group, Permission
from django.contrib.auth import get_user_model
from django_erp.configuration.models import Company, Currency, PaymentMethod
from django_erp.accounting.models import ExchangeRate
from django_erp.inventory.models import Location, Product
from django_erp.purchasing.models import Supplier
from django_erp.sales.models import Customer
from django_erp.accounting.models import Tax, TaxRate

User = get_user_model()

# Directorio donde están los archivos JSON
DATA_DIR = os.path.dirname(os.path.abspath(__file__))


def load_json_file(filename):
    """Carga un archivo JSON y lo devuelve como lista de diccionarios."""
    filepath = os.path.join(DATA_DIR, filename)
    if not os.path.exists(filepath):
        print(f"⚠️ Archivo no encontrado: {filepath}")
        return []
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


def get_or_create_companies():
    """Crea o actualiza las empresas definidas en los datos."""
    companies = {}
    data = load_json_file('00_companies.json')
    if not data:
        print("   ⚠️ No hay datos de empresas para cargar.")
        return companies
        
    for item in data:
        company_code = item.get('code')
        defaults = item.get('fields', {})
        parent_code = defaults.pop('parent_code', None)
        
        company, created = Company.objects.get_or_create(
            code=company_code,
            defaults=defaults
        )
        
        if parent_code and company.parent is None:
            parent = companies.get(parent_code)
            if parent:
                company.parent = parent
                company.save()
            else:
                print(f"   ⚠️ Empresa padre {parent_code} no encontrada para {company_code}")
        
        if created:
            print(f"   ✅ Empresa creada: {company.code} - {company.name}")
        else:
            print(f"   ℹ️ Empresa existente: {company.code}")
        companies[company_code] = company
    return companies


def load_currencies():
    """Carga las monedas (compartidas globalmente, sin empresa)."""
    data = load_json_file('01_currencies.json')
    if not data:
        print("   ⚠️ No hay datos de monedas para cargar.")
        return
    
    for item in data:
        fields = item.get('fields', {})
        currency_code = fields.get('code')
        if not currency_code:
            print(f"   ⚠️ Falta 'code' en moneda.")
            continue
        
        try:
            currency, created = Currency.objects.get_or_create(
                code=currency_code,
                defaults=fields
            )
            if created:
                print(f"   ✅ Moneda creada: {currency.code} - {currency.name}")
            else:
                print(f"   ℹ️ Moneda existente: {currency.code} - {currency.name}")
        except Exception as e:
            print(f"   ❌ Error creando moneda {currency_code}: {e}")


def load_exchange_rates(companies):
    """
    Carga las tasas de cambio para TODAS las empresas activas.
    """
    data = load_json_file('02_exchange_rates.json')
    
    # ✅ Valores por defecto
    if not data:
        print("   ⚠️ No hay datos en JSON. Usando valores por defecto.")
        rate_data = {
            'from_currency_code': 'USD',
            'to_currency_code': 'BS',
            'rate': 780.00,
            'effective_date': date.today().isoformat(),
            'source': 'Manual',
            'user_username': 'admin'
        }
    else:
        rate_data = data[0].get('fields', {})
    
    # ✅ Extraer datos
    from_currency_code = rate_data.get('from_currency_code', 'USD')
    to_currency_code = rate_data.get('to_currency_code', 'BS')
    rate_value = Decimal(str(rate_data.get('rate', 780.00)))
    source = rate_data.get('source', 'Manual')
    user_username = rate_data.get('user_username', 'admin')
    
    effective_date_str = rate_data.get('effective_date', date.today().isoformat())
    try:
        effective_date = datetime.strptime(effective_date_str, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        effective_date = date.today()
    
    today = date.today()
    
    # ✅ Buscar monedas
    try:
        from_currency = Currency.objects.get(code=from_currency_code)
        to_currency = Currency.objects.get(code=to_currency_code)
        print(f"   ✅ Monedas: {from_currency_code} -> {to_currency_code}")
    except Currency.DoesNotExist as e:
        print(f"   ❌ Error: {e}")
        return
    
    # ✅ Buscar usuario
    user = None
    if user_username:
        try:
            user = User.objects.get(username=user_username)
            print(f"   ✅ Usuario: {user_username}")
        except User.DoesNotExist:
            print(f"   ⚠️ Usuario no encontrado.")
    
    print(f"   📝 Tasa: {from_currency_code} -> {to_currency_code} = {rate_value}")
    
    companies_processed = 0
    for company_code, company in companies.items():
        if not company.is_active:
            continue
        
        # ✅ Eliminar todas las tasas existentes para esta empresa
        # (para asegurar que solo quede una)
        ExchangeRate.objects.filter(
            from_currency=from_currency,
            to_currency=to_currency,
            company=company
        ).delete()
        
        # ✅ Crear tasa nueva
        rate = ExchangeRate.objects.create(
            from_currency=from_currency,
            to_currency=to_currency,
            effective_date=effective_date,
            company=company,
            rate=rate_value,
            source=source,
            user=user,
            date=today,
        )
        print(f"   ✅ Tasa CREADA para {company_code}: {rate.rate}")
        companies_processed += 1
    
    print(f"   📊 Procesadas: {companies_processed} empresas")


def load_payment_methods(companies):
    """Carga los métodos de pago para cada empresa."""
    data = load_json_file('03_payment_methods.json')
    if not data:
        print("   ⚠️ No hay datos de métodos de pago para cargar.")
        return
        
    for item in data:
        company_code = item.get('company_code')
        company = companies.get(company_code)
        if not company:
            print(f"   ⚠️ Empresa {company_code} no encontrada para métodos de pago.")
            continue
            
        fields = item.get('fields', {})
        default_currency_code = fields.pop('default_currency_code', None)
        
        default_currency = None
        if default_currency_code:
            try:
                default_currency = Currency.objects.get(code=default_currency_code)
            except Currency.DoesNotExist:
                print(f"   ⚠️ Moneda por defecto {default_currency_code} no encontrada.")
        
        method_code = fields.get('code')
        if not method_code:
            print(f"   ⚠️ Falta 'code' en método de pago para {company_code}.")
            continue
        
        try:
            method, created = PaymentMethod.objects.get_or_create(
                code=method_code,
                company=company,
                defaults={
                    **fields,
                    'default_currency': default_currency,
                }
            )
            if created:
                print(f"   ✅ Método de pago creado: {method.code} para {company_code}")
            else:
                print(f"   ℹ️ Método de pago existente: {method.code} para {company_code}")
        except Exception as e:
            print(f"   ❌ Error creando método de pago: {e}")


def load_locations(companies):
    """Carga las ubicaciones para cada empresa."""
    data = load_json_file('04_locations.json')
    if not data:
        print("   ⚠️ No hay datos de ubicaciones para cargar.")
        return
        
    for item in data:
        company_code = item.get('company_code')
        company = companies.get(company_code)
        if not company:
            print(f"   ⚠️ Empresa {company_code} no encontrada para ubicaciones.")
            continue
            
        fields = item.get('fields', {})
        location_code = fields.get('code')
        if not location_code:
            print(f"   ⚠️ Falta 'code' en ubicación para {company_code}.")
            continue
            
        try:
            location, created = Location.objects.get_or_create(
                code=location_code,
                company=company,
                defaults=fields
            )
            if created:
                print(f"   ✅ Ubicación creada: {location.code} para {company_code}")
            else:
                print(f"   ℹ️ Ubicación existente: {location.code} para {company_code}")
        except Exception as e:
            print(f"   ❌ Error creando ubicación: {e}")


def load_products(companies):
    """Carga los productos para cada empresa."""
    data = load_json_file('05_products.json')
    if not data:
        print("   ⚠️ No hay datos de productos para cargar.")
        return
        
    for item in data:
        company_code = item.get('company_code')
        company = companies.get(company_code)
        if not company:
            print(f"   ⚠️ Empresa {company_code} no encontrada para productos.")
            continue
            
        fields = item.get('fields', {})
        product_code = fields.get('code')
        if not product_code:
            print(f"   ⚠️ Falta 'code' en producto para {company_code}.")
            continue
        
        # ✅ Asegurar que los campos de precio existen
        defaults = {
            'name': fields.get('name', ''),
            'description': fields.get('description', ''),
            'unit': fields.get('unit', 'UNIT'),
            'sale_price': fields.get('sale_price', 0.00),      # ✅ Precio de venta
            'purchase_price': fields.get('purchase_price', 0.00), # ✅ Precio de compra
            'is_service': fields.get('is_service', False),
            'is_active': fields.get('is_active', True),
        }
            
        try:
            product, created = Product.objects.get_or_create(
                code=product_code,
                company=company,
                defaults=defaults
            )
            if created:
                print(f"   ✅ Producto creado: {product.code} - {product.name} para {company_code}")
            else:
                # ✅ Actualizar si existe
                for key, value in defaults.items():
                    setattr(product, key, value)
                product.save()
                print(f"   ℹ️ Producto actualizado: {product.code} - {product.name} para {company_code}")
        except Exception as e:
            print(f"   ❌ Error creando producto {product_code}: {e}")


def load_suppliers(companies):
    """Carga los proveedores para cada empresa."""
    data = load_json_file('06_suppliers.json')
    if not data:
        print("   ⚠️ No hay datos de proveedores para cargar.")
        return
        
    for item in data:
        company_code = item.get('company_code')
        company = companies.get(company_code)
        if not company:
            print(f"   ⚠️ Empresa {company_code} no encontrada para proveedores.")
            continue
            
        fields = item.get('fields', {})
        tax_id = fields.get('tax_id')
        if not tax_id:
            print(f"   ⚠️ Falta 'tax_id' en proveedor para {company_code}.")
            continue
            
        try:
            supplier, created = Supplier.objects.get_or_create(
                tax_id=tax_id,
                company=company,
                defaults=fields
            )
            if created:
                print(f"   ✅ Proveedor creado: {supplier.name} para {company_code}")
            else:
                print(f"   ℹ️ Proveedor existente: {supplier.name} para {company_code}")
        except Exception as e:
            print(f"   ❌ Error creando proveedor: {e}")


def load_customers(companies):
    """Carga los clientes para cada empresa."""
    data = load_json_file('07_customers.json')
    if not data:
        print("   ⚠️ No hay datos de clientes para cargar.")
        return
        
    for item in data:
        company_code = item.get('company_code')
        company = companies.get(company_code)
        if not company:
            print(f"   ⚠️ Empresa {company_code} no encontrada para clientes.")
            continue
            
        fields = item.get('fields', {})
        tax_id = fields.get('tax_id')
        if not tax_id:
            print(f"   ⚠️ Falta 'tax_id' en cliente para {company_code}.")
            continue
            
        try:
            customer, created = Customer.objects.get_or_create(
                tax_id=tax_id,
                company=company,
                defaults=fields
            )
            if created:
                print(f"   ✅ Cliente creado: {customer.name} para {company_code}")
            else:
                print(f"   ℹ️ Cliente existente: {customer.name} para {company_code}")
        except Exception as e:
            print(f"   ❌ Error creando cliente: {e}")


def load_groups():
    """Carga los grupos (compartidos, sin empresa)."""
    data = load_json_file('09_groups.json')
    if not data:
        print("   ⚠️ No hay datos de grupos para cargar.")
        return
        
    for item in data:
        fields = item.get('fields', {})
        group_name = fields.get('name')
        if not group_name:
            print(f"   ⚠️ Falta 'name' en grupo.")
            continue
        
        try:
            group, created = Group.objects.get_or_create(
                name=group_name
            )
            if created:
                print(f"   ✅ Grupo creado: {group.name}")
            else:
                print(f"   ℹ️ Grupo existente: {group.name}")
            
            permission_ids = fields.get('permissions', [])
            if permission_ids:
                permissions = Permission.objects.filter(id__in=permission_ids)
                group.permissions.set(permissions)
        except Exception as e:
            print(f"   ❌ Error creando grupo: {e}")


def load_users(companies):
    """Carga los usuarios (compartidos, sin empresa)."""
    data = load_json_file('08_users.json')
    if not data:
        print("   ⚠️ No hay datos de usuarios para cargar.")
        return
        
    for item in data:
        username = item.get('username')
        if not username:
            print(f"   ⚠️ Falta 'username' en usuario.")
            continue
            
        fields = item.get('fields', {})
        company_codes = fields.pop('company_codes', [])
        groups_names = fields.pop('groups', [])
        
        password = fields.pop('password', None)
        if password and not password.startswith('pbkdf2_sha256'):
            fields['password'] = make_password(password)
        elif password:
            fields['password'] = password
        
        try:
            user, created = User.objects.get_or_create(
                username=username,
                defaults=fields
            )
            if created:
                print(f"   ✅ Usuario creado: {user.username}")
            else:
                print(f"   ℹ️ Usuario existente: {user.username}")
            
            for code in company_codes:
                company = companies.get(code)
                if company:
                    user.companies.add(company)
                    print(f"   ✅ Empresa {code} asignada a {user.username}")
                else:
                    print(f"   ⚠️ Empresa {code} no encontrada para {user.username}")
            
            for group_name in groups_names:
                try:
                    group = Group.objects.get(name=group_name)
                    user.groups.add(group)
                    print(f"   ✅ Grupo {group_name} asignado a {user.username}")
                except Group.DoesNotExist:
                    print(f"   ⚠️ Grupo {group_name} no encontrado para {user.username}")
            
            user.save()
        except Exception as e:
            print(f"   ❌ Error creando usuario {username}: {e}")

def load_taxes():
    """Carga los impuestos globales."""
    data = load_json_file('01_taxes.json')
    if not data:
        print("   ⚠️ No hay datos de impuestos para cargar.")
        return
    
    for item in data:
        fields = item.get('fields', {})
        tax_code = fields.get('code')
        if not tax_code:
            print(f"   ⚠️ Falta 'code' en impuesto.")
            continue
        
        tax, created = Tax.objects.get_or_create(
            code=tax_code,
            defaults=fields
        )
        if created:
            print(f"   ✅ Impuesto creado: {tax.code} - {tax.name}")
        else:
            print(f"   ℹ️ Impuesto existente: {tax.code} - {tax.name}")

def load_tax_rates(companies):
    """Carga las tasas de impuesto para cada empresa."""
    data = load_json_file('02_tax_rates.json')
    if not data:
        print("   ⚠️ No hay datos de tasas de impuesto para cargar.")
        return
        
    for item in data:
        company_code = item.get('company_code')
        company = companies.get(company_code)
        if not company:
            print(f"   ⚠️ Empresa {company_code} no encontrada para tasas de impuesto.")
            continue
            
        fields = item.get('fields', {})
        tax_code = fields.pop('tax_code', None)
        if not tax_code:
            print(f"   ⚠️ Falta 'tax_code' en tasa de impuesto para {company_code}.")
            continue
        
        try:
            tax = Tax.objects.get(code=tax_code)
        except Tax.DoesNotExist:
            print(f"   ⚠️ Impuesto {tax_code} no encontrado.")
            continue
        
        try:
            tax_rate, created = TaxRate.objects.get_or_create(
                tax=tax,
                company=company,
                effective_date=fields.get('effective_date'),
                defaults=fields
            )
            if created:
                print(f"   ✅ Tasa de impuesto creada: {tax_rate.tax.code} ({tax_rate.rate}%) para {company_code}")
            else:
                print(f"   ℹ️ Tasa de impuesto existente: {tax_rate.tax.code} ({tax_rate.rate}%) para {company_code}")
        except Exception as e:
            print(f"   ❌ Error creando tasa de impuesto: {e}")





@transaction.atomic
def load_all():
    """Carga todos los datos en orden."""
    print("=" * 70)
    print("📥 CARGANDO DATOS INICIALES (VERSIÓN FINAL)")
    print("=" * 70)
    
    print("\n🏢 CREANDO EMPRESAS...")
    companies = get_or_create_companies()
    
    print("\n👥 CARGANDO GRUPOS (COMPARTIDOS)...")
    load_groups()
    
    print("\n💱 CARGANDO MONEDAS...")
    load_currencies()
    
    print("\n💰 CARGANDO TASAS DE CAMBIO...")
    load_exchange_rates(companies)
    
    print("\n💳 CARGANDO MÉTODOS DE PAGO...")
    load_payment_methods(companies)
    
    print("\n📍 CARGANDO UBICACIONES...")
    load_locations(companies)
    
    print("\n📦 CARGANDO PRODUCTOS...")
    load_products(companies)
    
    print("\n🤝 CARGANDO PROVEEDORES...")
    load_suppliers(companies)
    
    print("\n👤 CARGANDO CLIENTES...")
    load_customers(companies)
    
    print("\n👥 CARGANDO USUARIOS...")
    load_users(companies)
    
    print("\n" + "=" * 70)
    print("✅ CARGA COMPLETADA EXITOSAMENTE")
    print("=" * 70)

    print("\n📊 CARGANDO IMPUESTOS (CONTABILIDAD)...")
    load_taxes()
    
    print("\n📊 CARGANDO TASAS DE IMPUESTO (CONTABILIDAD)...")
    load_tax_rates(companies)


if __name__ == "__main__":
    load_all()