# configuration/data/load_data.py
"""
Script para cargar datos iniciales en ambas bases de datos (PostgreSQL y SQLite)
Uso: 
    python -m django_erp.configuration.data.load_data              # Carga en ambas
    python -m django_erp.configuration.data.load_data default      # Solo PostgreSQL
    python -m django_erp.configuration.data.load_data local        # Solo SQLite
"""

import os
import sys
import django

# ✅ CONFIGURAR DJANGO PRIMERO
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'django_erp.settings')
django.setup()

# ✅ AHORA SÍ, importar el resto
import json
from django.contrib.auth.models import Group, Permission
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.db import connections
from django.core.management import call_command

# ✅ Importar modelos
from django_erp.configuration.models import Currency, ExchangeRate
from django_erp.sales.models import Customer
from django_erp.warehouse.models import Product, Location

User = get_user_model()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, 'data')


def load_currencies(database='default'):
    """
    Cargar monedas desde JSON en la base de datos especificada
    
    Args:
        database: 'default' (PostgreSQL) o 'local' (SQLite)
    """
    print(f"📥 Cargando monedas en {database}...")
    file_path = os.path.join(DATA_DIR, 'currencies.json')
    
    if not os.path.exists(file_path):
        print(f"⚠️ No se encontró currencies.json")
        return 0
    
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    count = 0
    for item in data:
        fields = item['fields']
        
        # ✅ Usar la base de datos especificada
        currency, created = Currency.objects.using(database).get_or_create(
            code=fields['code'],
            defaults={
                'name': fields['name'],
                'symbol': fields['symbol'],
                'decimal_places': fields.get('decimal_places', 2),
                'is_base': fields.get('is_base', False),
                'is_active': fields.get('is_active', True),
            }
        )
        if created:
            count += 1
            print(f"   ✅ Creada: {currency.code} - {currency.name}")
    
    print(f"✅ Monedas cargadas en {database}: {count} nuevas")
    return count


def load_exchange_rates(database='default'):
    """Cargar tasas de cambio desde JSON en la base de datos especificada"""
    print(f"📥 Cargando tasas de cambio en {database}...")
    file_path = os.path.join(DATA_DIR, 'exchange_rates.json')
    
    if not os.path.exists(file_path):
        print(f"⚠️ No se encontró exchange_rates.json")
        return 0
    
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    count = 0
    for item in data:
        fields = item['fields']
        try:
            # ✅ Usar la base de datos especificada
            from_currency = Currency.objects.using(database).get(pk=fields['from_currency'])
            to_currency = Currency.objects.using(database).get(pk=fields['to_currency'])
            
            rate, created = ExchangeRate.objects.using(database).get_or_create(
                from_currency=from_currency,
                to_currency=to_currency,
                date=fields['date'],
                defaults={
                    'rate': fields['rate'],
                    'source': fields.get('source', ''),
                    'user_id': fields.get('user'),
                }
            )
            if created:
                count += 1
                print(f"   ✅ Creada: {from_currency.code} → {to_currency.code} = {fields['rate']}")
        except Currency.DoesNotExist:
            print(f"   ⚠️ Moneda no encontrada: {fields['from_currency']}")
    
    print(f"✅ Tasas cargadas en {database}: {count} nuevas")
    return count


def load_groups(database='default'):
    """
    Cargar grupos desde JSON en la base de datos especificada
    ⚠️ SOLO se usa en PostgreSQL (por seguridad)
    """
    print(f"📥 Cargando grupos en {database}...")
    file_path = os.path.join(DATA_DIR, 'groups.json')
    
    if not os.path.exists(file_path):
        print(f"⚠️ No se encontró groups.json")
        return 0
    
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    count = 0
    for item in data:
        fields = item['fields']
        group, created = Group.objects.using(database).get_or_create(
            name=fields['name'],
            defaults={}
        )
        if created:
            count += 1
            print(f"   ✅ Creado: {group.name}")
        
        if fields.get('permissions'):
            permissions = Permission.objects.using(database).filter(pk__in=fields['permissions'])
            group.permissions.set(permissions)
    
    print(f"✅ Grupos cargados en {database}: {count} nuevos")
    return count


def load_users(database='default'):
    """
    Cargar usuarios desde JSON en la base de datos especificada
    ⚠️ SOLO se usa en PostgreSQL (por seguridad)
    """
    print(f"📥 Cargando usuarios en {database}...")
    file_path = os.path.join(DATA_DIR, 'users.json')
    
    if not os.path.exists(file_path):
        print(f"⚠️ No se encontró users.json")
        return 0
    
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    count = 0
    for item in data:
        fields = item['fields']
        user, created = User.objects.using(database).get_or_create(
            username=fields['username'],
            defaults={
                'password': fields['password'],
                'email': fields.get('email', ''),
                'first_name': fields.get('first_name', ''),
                'last_name': fields.get('last_name', ''),
                'is_active': fields.get('is_active', True),
                'is_staff': fields.get('is_staff', False),
                'is_superuser': fields.get('is_superuser', False),
            }
        )
        if created:
            count += 1
            print(f"   ✅ Creado: {user.username}")
        
        if fields.get('groups'):
            groups = Group.objects.using(database).filter(pk__in=fields['groups'])
            user.groups.set(groups)
        
        if fields.get('user_permissions'):
            permissions = Permission.objects.using(database).filter(pk__in=fields['user_permissions'])
            user.user_permissions.set(permissions)
    
    print(f"✅ Usuarios cargados en {database}: {count} nuevos")
    return count


def load_all():
    """Cargar todos los datos en AMBAS bases de datos"""
    print("=" * 60)
    print("📥 CARGANDO DATOS EN AMBAS BASES DE DATOS")
    print("=" * 60)
    
    if not os.path.exists(DATA_DIR):
        print("⚠️ No existe el directorio data/")
        return
    
    # ✅ Verificar que ambas bases de datos existen
    try:
        connections['default'].ensure_connection()
        print("✅ PostgreSQL (default) conectado")
    except Exception as e:
        print(f"❌ Error conectando a PostgreSQL: {e}")
        return
    
    try:
        connections['local'].ensure_connection()
        print("✅ SQLite (local) conectado")
    except Exception as e:
        print(f"❌ Error conectando a SQLite: {e}")
        return
    
    # ============================================================
    # ✅ Cargar en PostgreSQL (TODOS los datos)
    # ============================================================
    print("\n" + "=" * 60)
    print("📦 PostgreSQL (default) - TODOS LOS DATOS")
    print("=" * 60)
    
    with transaction.atomic(using='default'):
        load_currencies('default')
        load_exchange_rates('default')
        load_groups('default')      # ✅ Grupos SOLO en PostgreSQL
        load_users('default')       # ✅ Usuarios SOLO en PostgreSQL
    
    # ============================================================
    # ✅ Cargar en SQLite (SOLO datos necesarios para facturar offline)
    # ============================================================
    print("\n" + "=" * 60)
    print("📦 SQLite (local) - SOLO DATOS DE FACTURACIÓN")
    print("=" * 60)
    
    with transaction.atomic(using='local'):
        load_currencies('local')        # ✅ Monedas (necesarias offline)
        load_exchange_rates('local')    # ✅ Tasas de cambio (necesarias offline)
        # ❌ NO cargar grupos en SQLite (no son necesarios para facturar)
        # ❌ NO cargar usuarios en SQLite (por seguridad)
        print("   ⏭️  Grupos: omitidos en SQLite (solo PostgreSQL)")
        print("   ⏭️  Usuarios: omitidos en SQLite (solo PostgreSQL)")
    
    # ============================================================
    # ✅ Verificar que los datos se cargaron correctamente
    # ============================================================
    print("\n" + "=" * 60)
    print("🔍 VERIFICANDO DATOS")
    print("=" * 60)
    
    from django_erp.configuration.models import Currency
    
    pg_count = Currency.objects.using('default').count()
    sqlite_count = Currency.objects.using('local').count()
    
    print(f"📊 Monedas en PostgreSQL: {pg_count}")
    print(f"📊 Monedas en SQLite: {sqlite_count}")
    
    if pg_count == sqlite_count and pg_count > 0:
        print("\n🎉 ¡AMBAS BASES DE DATOS TIENEN LAS MISMAS MONEDAS!")
    else:
        print("\n⚠️ LAS BASES DE DATOS NO COINCIDEN")
        print(f"   Diferencia: {abs(pg_count - sqlite_count)} registros")
    
    # ✅ Verificar usuarios (solo en PostgreSQL)
    user_count = User.objects.using('default').count()
    print(f"\n👤 Usuarios en PostgreSQL: {user_count}")
    
    print("\n" + "=" * 60)
    print("✅ CARGA COMPLETADA")
    print("=" * 60)


def load_single(database='default'):
    """
    Cargar datos en UNA base de datos específica
    
    Args:
        database: 'default' o 'local'
    """
    print("=" * 60)
    print(f"📥 CARGANDO DATOS EN {database.upper()}")
    print("=" * 60)
    
    if not os.path.exists(DATA_DIR):
        print("⚠️ No existe el directorio data/")
        return
    
    with transaction.atomic(using=database):
        load_currencies(database)
        load_exchange_rates(database)
        
        # ✅ Solo cargar grupos y usuarios en PostgreSQL
        if database == 'default':
            load_groups(database)
            load_users(database)
        else:
            print("   ⏭️  Grupos y usuarios: omitidos en SQLite (solo PostgreSQL)")
    
    print("=" * 60)
    print(f"✅ CARGA COMPLETADA EN {database.upper()}")
    print("=" * 60)


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1:
        db = sys.argv[1]
        if db in ['default', 'local']:
            load_single(db)
        else:
            print("❌ Argumento inválido. Usa 'default' o 'local'")
    else:
        load_all()