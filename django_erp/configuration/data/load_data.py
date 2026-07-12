# configuration/scripts/load_data.py
import json
import os
from django.contrib.auth.models import Group, Permission
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction

# ✅ Importar modelos desde django_erp
from django_erp.configuration.models import Currency, ExchangeRate

User = get_user_model()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, 'data')


@transaction.atomic
def load_currencies():
    """Cargar monedas desde JSON"""
    print("📥 Cargando monedas...")
    file_path = os.path.join(DATA_DIR, 'currencies.json')
    
    if not os.path.exists(file_path):
        print("⚠️ No se encontró currencies.json")
        return
    
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


@transaction.atomic
def load_exchange_rates():
    """Cargar tasas de cambio desde JSON"""
    print("📥 Cargando tasas de cambio...")
    file_path = os.path.join(DATA_DIR, 'exchange_rates.json')
    
    if not os.path.exists(file_path):
        print("⚠️ No se encontró exchange_rates.json")
        return
    
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
            print(f"   ⚠️ Moneda no encontrada: {fields['from_currency']} o {fields['to_currency']}")
    
    print(f"✅ Tasas cargadas: {count} nuevas")


@transaction.atomic
def load_groups():
    """Cargar grupos desde JSON"""
    print("📥 Cargando grupos...")
    file_path = os.path.join(DATA_DIR, 'groups.json')
    
    if not os.path.exists(file_path):
        print("⚠️ No se encontró groups.json")
        return
    
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


@transaction.atomic
def load_users():
    """Cargar usuarios desde JSON"""
    print("📥 Cargando usuarios...")
    file_path = os.path.join(DATA_DIR, 'users.json')
    
    if not os.path.exists(file_path):
        print("⚠️ No se encontró users.json")
        return
    
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


def load_all():
    """Cargar todos los datos"""
    print("=" * 50)
    print("📥 CARGANDO DATOS DE CONFIGURACIÓN")
    print("=" * 50)
    
    if not os.path.exists(DATA_DIR):
        print("⚠️ No existe el directorio data/")
        return
    
    load_currencies()
    load_exchange_rates()
    load_groups()
    load_users()
    
    print("=" * 50)
    print("✅ Carga completada")
    print("=" * 50)


if __name__ == '__main__':
    load_all()