# configuration/scripts/export_data.py
import json
import os
from django.contrib.auth.models import Group, Permission
from django.contrib.auth import get_user_model
from django.core.serializers import serialize
from django.apps import apps

# ✅ Importar modelos desde django_erp
from django_erp.configuration.models import Currency, ExchangeRate

User = get_user_model()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, 'data')


def export_currencies():
    """Exportar monedas a JSON"""
    print("📤 Exportando monedas...")
    data = []
    for currency in Currency.objects.all():
        data.append({
            'model': 'django_erp.configuration.currency',
            'pk': currency.pk,
            'fields': {
                'code': currency.code,
                'name': currency.name,
                'symbol': currency.symbol,
                'decimal_places': currency.decimal_places,
                'is_base': currency.is_base,
                'is_active': currency.is_active,
            }
        })
    
    file_path = os.path.join(DATA_DIR, 'currencies.json')
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"✅ Monedas exportadas: {len(data)} registros → {file_path}")


def export_exchange_rates():
    """Exportar tasas de cambio a JSON"""
    print("📤 Exportando tasas de cambio...")
    data = []
    for rate in ExchangeRate.objects.all():
        data.append({
            'model': 'django_erp.configuration.exchangerate',
            'pk': rate.pk,
            'fields': {
                'from_currency': rate.from_currency.pk,
                'to_currency': rate.to_currency.pk,
                'rate': str(rate.rate),
                'date': rate.date.isoformat(),
                'source': rate.source,
                'user': rate.user.pk if rate.user else None,
            }
        })
    
    file_path = os.path.join(DATA_DIR, 'exchange_rates.json')
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"✅ Tasas exportadas: {len(data)} registros → {file_path}")


def export_groups():
    """Exportar grupos y permisos a JSON"""
    print("📤 Exportando grupos...")
    data = []
    for group in Group.objects.all():
        data.append({
            'model': 'auth.group',
            'pk': group.pk,
            'fields': {
                'name': group.name,
                'permissions': [p.pk for p in group.permissions.all()],
            }
        })
    
    file_path = os.path.join(DATA_DIR, 'groups.json')
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"✅ Grupos exportados: {len(data)} registros → {file_path}")


def export_permissions():
    """Exportar permisos a JSON"""
    print("📤 Exportando permisos...")
    data = []
    for permission in Permission.objects.all():
        data.append({
            'model': 'auth.permission',
            'pk': permission.pk,
            'fields': {
                'name': permission.name,
                'content_type': permission.content_type.pk,
                'codename': permission.codename,
            }
        })
    
    file_path = os.path.join(DATA_DIR, 'permissions.json')
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"✅ Permisos exportados: {len(data)} registros → {file_path}")


def export_users():
    """Exportar usuarios a JSON"""
    print("📤 Exportando usuarios...")
    data = []
    for user in User.objects.all():
        data.append({
            'model': 'django_erp.users.user',
            'pk': user.pk,
            'fields': {
                'username': user.username,
                'password': user.password,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'is_active': user.is_active,
                'is_staff': user.is_staff,
                'is_superuser': user.is_superuser,
                'last_login': user.last_login.isoformat() if user.last_login else None,
                'date_joined': user.date_joined.isoformat(),
                'groups': [g.pk for g in user.groups.all()],
                'user_permissions': [p.pk for p in user.user_permissions.all()],
            }
        })
    
    file_path = os.path.join(DATA_DIR, 'users.json')
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"✅ Usuarios exportados: {len(data)} registros → {file_path}")


def export_all():
    """Exportar todos los datos"""
    print("=" * 50)
    print("📤 EXPORTANDO DATOS DE CONFIGURACIÓN")
    print("=" * 50)
    
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
    
    export_currencies()
    export_exchange_rates()
    export_groups()
    export_permissions()
    export_users()
    
    print("=" * 50)
    print("✅ Exportación completada")
    print("=" * 50)


if __name__ == '__main__':
    export_all()