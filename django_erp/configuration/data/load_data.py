# configuration/data/load_data.py
"""
Script para cargar datos iniciales SOLO en la base de datos default (SQLite)
Uso: 
    python -m django_erp.configuration.data.load_data
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

# ✅ Importar modelos
from django_erp.configuration.models import Currency, ExchangeRate, PaymentMethod

User = get_user_model()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, 'data')


def load_currencies():
    """Cargar monedas desde JSON en la base de datos default"""
    print("📥 Cargando monedas...")
    file_path = os.path.join(DATA_DIR, 'currencies.json')
    
    if not os.path.exists(file_path):
        print(f"⚠️ No se encontró currencies.json")
        return 0
    
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    count = 0
    for item in data:
        fields = item['fields']
        currency, created = Currency.objects.get_or_create(
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
    
    print(f"✅ Monedas cargadas: {count} nuevas")
    return count


def load_exchange_rates():
    """Cargar tasas de cambio desde JSON"""
    print("📥 Cargando tasas de cambio...")
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
            from_currency = Currency.objects.get(pk=fields['from_currency'])
            to_currency = Currency.objects.get(pk=fields['to_currency'])
            
            rate, created = ExchangeRate.objects.get_or_create(
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
    
    print(f"✅ Tasas cargadas: {count} nuevas")
    return count


def load_groups():
    """Cargar grupos desde JSON"""
    print("📥 Cargando grupos...")
    file_path = os.path.join(DATA_DIR, 'groups.json')
    
    if not os.path.exists(file_path):
        print(f"⚠️ No se encontró groups.json")
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


def load_users():
    """Cargar usuarios desde JSON"""
    print("📥 Cargando usuarios...")
    file_path = os.path.join(DATA_DIR, 'users.json')
    
    if not os.path.exists(file_path):
        print(f"⚠️ No se encontró users.json")
        return 0
    
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    count = 0
    for item in data:
        fields = item['fields']
        user, created = User.objects.get_or_create(
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
            groups = Group.objects.filter(pk__in=fields['groups'])
            user.groups.set(groups)
        
        if fields.get('user_permissions'):
            permissions = Permission.objects.filter(pk__in=fields['user_permissions'])
            user.user_permissions.set(permissions)
    
    print(f"✅ Usuarios cargados: {count} nuevos")
    return count


def load_payment_methods():
    """Cargar métodos de pago desde JSON"""
    print("📥 Cargando métodos de pago...")
    file_path = os.path.join(DATA_DIR, 'payment_methods.json')
    
    if not os.path.exists(file_path):
        print(f"⚠️ No se encontró payment_methods.json")
        return 0
    
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    count = 0
    for item in data:
        fields = item['fields']
        method, created = PaymentMethod.objects.get_or_create(
            code=fields['code'],
            defaults={
                'name': fields['name'],
                'description': fields.get('description', ''),
                'is_active': fields.get('is_active', True),
                'requires_approval': fields.get('requires_approval', False),
                'icon': fields.get('icon', ''),
            }
        )
        if created:
            count += 1
            print(f"   ✅ Creado: {method.name} ({method.code})")
    
    print(f"✅ Métodos de pago cargados: {count} nuevos")
    return count


def load_all():
    """Cargar todos los datos en la base de datos default"""
    print("=" * 60)
    print("📥 CARGANDO DATOS INICIALES")
    print("=" * 60)
    
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
    
    # ✅ Cargar todos los datos
    with transaction.atomic():
        load_currencies()
        load_exchange_rates()
        load_groups()
        load_users()
        load_payment_methods()
    
    # ✅ Verificar
    print("\n" + "=" * 60)
    print("🔍 VERIFICANDO DATOS")
    print("=" * 60)
    
    print(f"📊 Monedas: {Currency.objects.count()}")
    print(f"👤 Usuarios: {User.objects.count()}")
    print(f"💳 Métodos de Pago: {PaymentMethod.objects.count()}")
    
    print("\n" + "=" * 60)
    print("✅ CARGA COMPLETADA")
    print("=" * 60)


if __name__ == '__main__':
    load_all()