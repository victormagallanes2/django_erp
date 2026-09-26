# django_erp/configuration/data/load_data_prod.py
"""
Carga de datos básicos para producción + grupos y permisos.

Uso:
    python -m django_erp.configuration.data.load_data_prod

Idempotente: se puede correr múltiples veces sin duplicar.
"""

import os
import sys
import django
from decimal import Decimal
from datetime import date, datetime

# ============================================================
# Configuración de Django (ANTES de importar modelos)
# ============================================================
sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'django_erp.settings')
django.setup()

# ============================================================
# Imports (después de django.setup())
# ============================================================
from django.db import transaction
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType

from django_erp.configuration.models import (
    Company,
    Currency,
    PaymentMethod,
)
from django_erp.accounting.models import (
    ExchangeRate,
    Tax,
    TaxRate,
)
from django_erp.inventory.models import Location

User = get_user_model()


# ============================================================
# DATOS EN DURO
# ============================================================
COMPANY_DATA = {
    "code": "01",
    "fields": {
        "name": "Compañia Default",
        "rif": "J-00000000-0",
        "trade_name": "Nombre Default",
        "address": "Direccion Default",
        "phone": "+000000000000",
        "email": "company@company.com",
        "default_currency_code": "USD",
        "invoice_prefix": "FAC",
        "is_main": True,
        "is_active": True,
    },
}

CURRENCIES_DATA = [
    {
        "code": "USD",
        "name": "Dólar Americano",
        "symbol": "$",
        "decimal_places": 2,
        "is_base": True,
        "is_active": True,
    },
    {
        "code": "BS",
        "name": "Bolívar Soberano",
        "symbol": "Bs.",
        "decimal_places": 2,
        "is_base": False,
        "is_active": True,
    },
]

EXCHANGE_RATES_DATA = [
    {
        "from_currency_code": "USD",
        "to_currency_code": "BS",
        "rate": Decimal("780.00"),
        "effective_date": "2026-09-02",
        "source": "BCV",
        "user_username": "admin",
    },
]

TAXES_DATA = [
    {
        "code": "VAT",
        "name": "Impuesto al Valor Agregado",
        "tax_type": "SALES",
        "is_active": True,
    },
]

TAX_RATES_DATA = [
    {
        "tax_code": "VAT",
        "rate": Decimal("16.00"),
        "effective_date": "2024-01-01",
        "is_default": True,
        "note": "Tasa de IVA estándar para Venezuela",
    },
]

PAYMENT_METHODS_DATA = [
    {
        "name": "Efectivo (Bs.)",
        "code": "CASH_BS",
        "description": "Pago en efectivo en Bolívares",
        "requires_company_bank": False,
        "requires_reference": False,
        "requires_approval": False,
        "default_currency_code": "BS",
        "is_active": True,
    },
    {
        "name": "Efectivo (USD)",
        "code": "CASH_USD",
        "description": "Pago en efectivo en Dólares",
        "requires_company_bank": False,
        "requires_reference": False,
        "requires_approval": False,
        "default_currency_code": "USD",
        "is_active": True,
    },
    {
        "name": "Transferencia Bancaria",
        "code": "BANK_TRANSFER",
        "description": "Transferencia bancaria",
        "requires_company_bank": True,
        "requires_reference": True,
        "requires_approval": True,
        "default_currency_code": "USD",
        "is_active": True,
    },
    {
        "name": "Pago Móvil",
        "code": "MOBILE_PAYMENT",
        "description": "Pago móvil",
        "requires_company_bank": False,
        "requires_reference": True,
        "requires_approval": False,
        "default_currency_code": "BS",
        "is_active": True,
    },
]

LOCATIONS_DATA = [
    {
        "code": "ALM-01",
        "name": "Almacén Principal",
        "description": "Almacén principal",
        "is_active": True,
    },
]


# ============================================================
# HELPERS
# ============================================================
def parse_date(value):
    if isinstance(value, date):
        return value
    if not value:
        return date.today()
    try:
        return datetime.strptime(str(value), "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return date.today()


def get_admin_user():
    user = User.objects.filter(username="admin").first()
    if user:
        return user
    return User.objects.filter(is_superuser=True).first()


def _perms(app_label, model_name, actions):
    """
    Devuelve las Permission para un modelo y acciones dadas.
    Ej: _perms('sales', 'Customer', ['view','add','change'])
    """
    model = model_name.lower()
    try:
        ct = ContentType.objects.get(app_label=app_label, model=model)
    except ContentType.DoesNotExist:
        print(f"   ⚠️ ContentType no encontrado: {app_label}.{model_name}")
        return []
    return list(
        Permission.objects.filter(
            content_type=ct,
            codename__in=[f"{a}_{model}" for a in actions],
        )
    )


def _custom_perm(app_label, model_name, codename):
    """Devuelve una Permission personalizada (Meta.permissions)."""
    model = model_name.lower()
    try:
        ct = ContentType.objects.get(app_label=app_label, model=model)
        return Permission.objects.get(content_type=ct, codename=codename)
    except (ContentType.DoesNotExist, Permission.DoesNotExist):
        print(f"   ⚠️ Permiso custom no encontrado: {app_label}.{codename}")
        return None


def _add_perms(group, *perm_lists):
    """Añade permisos a un grupo ignorando None."""
    flat = []
    for p in perm_lists:
        if p is None:
            continue
        if isinstance(p, list):
            flat.extend(p)
        else:
            flat.append(p)
    flat = [p for p in flat if p is not None]
    if flat:
        group.permissions.add(*flat)


# ============================================================
# 1. MONEDAS
# ============================================================
def load_currencies():
    print("\n💱 Cargando monedas...")
    created = updated = 0
    for item in CURRENCIES_DATA:
        code = item["code"]
        defaults = {k: v for k, v in item.items() if k != "code"}
        currency, was_created = Currency.objects.update_or_create(
            code=code, defaults=defaults
        )
        if was_created:
            created += 1
            print(f"   ✅ Moneda creada: {currency.code} - {currency.name}")
        else:
            updated += 1
            print(f"   ℹ️ Moneda actualizada: {currency.code} - {currency.name}")
    print(f"   📊 Total: {created} creadas, {updated} actualizadas")


# ============================================================
# 2. EMPRESA
# ============================================================
def load_company():
    print("\n🏢 Cargando empresa...")
    code = COMPANY_DATA["code"]
    fields = COMPANY_DATA["fields"].copy()

    default_currency_code = fields.pop("default_currency_code", None)
    if default_currency_code:
        try:
            fields["default_currency"] = Currency.objects.get(code=default_currency_code)
        except Currency.DoesNotExist:
            print(f"   ⚠️ Moneda {default_currency_code} no encontrada")
            fields["default_currency"] = None

    company, created = Company.objects.update_or_create(code=code, defaults=fields)
    if created:
        print(f"   ✅ Empresa creada: {company.code} - {company.name}")
    else:
        print(f"   ℹ️ Empresa actualizada: {company.code} - {company.name}")

    admin = get_admin_user()
    if admin and hasattr(admin, "companies"):
        admin.companies.add(company)
        print(f"   ✅ Admin '{admin.username}' asignado a la empresa")

    return company


# ============================================================
# 3. TASAS DE CAMBIO
# ============================================================
def load_exchange_rates(company):
    print("\n💵 Cargando tasas de cambio...")
    admin = get_admin_user()
    today = date.today()

    for item in EXCHANGE_RATES_DATA:
        try:
            from_currency = Currency.objects.get(code=item["from_currency_code"])
            to_currency = Currency.objects.get(code=item["to_currency_code"])
        except Currency.DoesNotExist as e:
            print(f"   ❌ Moneda no encontrada: {e}")
            continue

        effective_date = parse_date(item["effective_date"])

        existing = ExchangeRate.objects.filter(
            company=company,
            from_currency=from_currency,
            to_currency=to_currency,
            effective_date=effective_date,
        ).first()

        if existing:
            existing.rate = item["rate"]
            existing.source = item.get("source", "Manual")
            existing.user = admin
            existing.save()
            print(f"   ℹ️ Tasa actualizada: 1 {from_currency.code} = "
                  f"{existing.rate} {to_currency.code} ({effective_date})")
        else:
            rate = ExchangeRate.objects.create(
                from_currency=from_currency,
                to_currency=to_currency,
                rate=item["rate"],
                effective_date=effective_date,
                source=item.get("source", "Manual"),
                user=admin,
                company=company,
                date=today,
            )
            print(f"   ✅ Tasa creada: 1 {from_currency.code} = "
                  f"{rate.rate} {to_currency.code} ({effective_date})")


# ============================================================
# 4. IMPUESTOS
# ============================================================
def load_taxes():
    print("\n📊 Cargando impuestos...")
    for item in TAXES_DATA:
        code = item["code"]
        defaults = {k: v for k, v in item.items() if k != "code"}
        tax, created = Tax.objects.update_or_create(code=code, defaults=defaults)
        if created:
            print(f"   ✅ Impuesto creado: {tax.code} - {tax.name}")
        else:
            print(f"   ℹ️ Impuesto actualizado: {tax.code} - {tax.name}")


# ============================================================
# 5. TASAS DE IMPUESTO
# ============================================================
def load_tax_rates(company):
    print("\n📊 Cargando tasas de impuesto...")
    for item in TAX_RATES_DATA:
        try:
            tax = Tax.objects.get(code=item["tax_code"])
        except Tax.DoesNotExist:
            print(f"   ❌ Impuesto {item['tax_code']} no encontrado")
            continue

        effective_date = parse_date(item["effective_date"])

        tax_rate, created = TaxRate.objects.update_or_create(
            tax=tax,
            company=company,
            effective_date=effective_date,
            defaults={
                "rate": item["rate"],
                "is_default": item.get("is_default", False),
                "note": item.get("note", ""),
            },
        )
        if created:
            print(f"   ✅ Tasa creada: {tax_rate.tax.code} ({tax_rate.rate}%) "
                  f"para {company.code} desde {effective_date}")
        else:
            print(f"   ℹ️ Tasa actualizada: {tax_rate.tax.code} ({tax_rate.rate}%) "
                  f"para {company.code}")


# ============================================================
# 6. MÉTODOS DE PAGO
# ============================================================
def load_payment_methods(company):
    print("\n💳 Cargando métodos de pago...")
    for item in PAYMENT_METHODS_DATA:
        code = item["code"]
        fields = {k: v for k, v in item.items() if k != "code"}

        default_currency_code = fields.pop("default_currency_code", None)
        default_currency = None
        if default_currency_code:
            try:
                default_currency = Currency.objects.get(code=default_currency_code)
            except Currency.DoesNotExist:
                print(f"   ⚠️ Moneda {default_currency_code} no encontrada")

        method, created = PaymentMethod.objects.update_or_create(
            code=code,
            company=company,
            defaults={**fields, "default_currency": default_currency},
        )
        if created:
            print(f"   ✅ Método creado: {method.code} - {method.name}")
        else:
            print(f"   ℹ️ Método actualizado: {method.code} - {method.name}")


# ============================================================
# 7. UBICACIONES
# ============================================================
def load_locations(company):
    print("\n📍 Cargando ubicaciones...")
    for item in LOCATIONS_DATA:
        code = item["code"]
        fields = {k: v for k, v in item.items() if k != "code"}
        location, created = Location.objects.update_or_create(
            code=code, company=company, defaults=fields
        )
        if created:
            print(f"   ✅ Ubicación creada: {location.code} - {location.name}")
        else:
            print(f"   ℹ️ Ubicación actualizada: {location.code} - {location.name}")


# ============================================================
# 8. GRUPOS Y PERMISOS
# ============================================================
def load_groups():
    print("\n👥 Cargando grupos y permisos...")

    # --------------------------------------------------------
    # VENTAS
    # --------------------------------------------------------
    ventas, _ = Group.objects.get_or_create(name="Ventas")
    ventas.permissions.clear()
    _add_perms(
        ventas,
        _perms("sales", "Customer", ["view", "add", "change"]),
        _perms("sales", "SaleOrder", ["view", "add", "change"]),
        _perms("sales", "SaleInvoice", ["view", "add", "change"]),
        _perms("sales", "Payment", ["view", "add"]),
        _perms("sales", "CashRegister", ["view", "add", "change"]),
        _perms("sales", "CashTransaction", ["view"]),
        _perms("inventory", "Product", ["view"]),
        _perms("inventory", "Inventory", ["view"]),
        _perms("inventory", "Location", ["view"]),
        _perms("rrhh", "Commission", ["view"]),
        _perms("accounting", "ExchangeRate", ["view"]),
        _perms("configuration", "PaymentMethod", ["view"]),
        _perms("configuration", "Currency", ["view"]),
    )
    print(f"   ✅ Grupo 'Ventas' → {ventas.permissions.count()} permisos")

    # --------------------------------------------------------
    # ALMACÉN
    # --------------------------------------------------------
    almacen, _ = Group.objects.get_or_create(name="Almacén")
    almacen.permissions.clear()
    _add_perms(
        almacen,
        _perms("inventory", "Product", ["view"]),
        _perms("inventory", "Location", ["view", "add", "change"]),
        _perms("inventory", "Movement", ["view", "add", "change"]),
        _perms("inventory", "Inventory", ["view", "change"]),
        _perms("inventory", "PhysicalCount", ["view", "add"]),
        _perms("inventory", "DeliveryNote", ["view", "add", "change"]),
        _custom_perm("inventory", "DeliveryNote", "can_confirm_deliverynote"),
        _perms("inventory", "ReceiptNote", ["view", "add", "change"]),
        _custom_perm("inventory", "ReceiptNote", "can_confirm_receiptnote"),
        _perms("purchasing", "PurchaseOrder", ["view"]),
        _perms("purchasing", "Supplier", ["view"]),
    )
    print(f"   ✅ Grupo 'Almacén' → {almacen.permissions.count()} permisos")

    # --------------------------------------------------------
    # COMPRAS
    # --------------------------------------------------------
    compras, _ = Group.objects.get_or_create(name="Compras")
    compras.permissions.clear()
    _add_perms(
        compras,
        _perms("purchasing", "Supplier", ["view", "add", "change"]),
        _perms("purchasing", "PurchaseOrder", ["view", "add", "change"]),
        _custom_perm("purchasing", "PurchaseOrder", "can_confirm_order"),
        _custom_perm("purchasing", "PurchaseOrder", "can_cancel_order"),
        _perms("purchasing", "PurchaseInvoice", ["view", "add", "change"]),
        _perms("purchasing", "PurchasePayment", ["view", "add"]),
        _perms("inventory", "Product", ["view"]),
        _perms("inventory", "ReceiptNote", ["view"]),
        _perms("accounting", "ExchangeRate", ["view"]),
        _perms("configuration", "CompanyBankAccount", ["view"]),
        _perms("configuration", "PaymentMethod", ["view"]),
    )
    print(f"   ✅ Grupo 'Compras' → {compras.permissions.count()} permisos")

    # --------------------------------------------------------
    # CONTABILIDAD
    # --------------------------------------------------------
    contab, _ = Group.objects.get_or_create(name="Contabilidad")
    contab.permissions.clear()
    _add_perms(
        contab,
        _perms("accounting", "Tax", ["view", "add", "change"]),
        _perms("accounting", "TaxRate", ["view", "add", "change"]),
        _perms("accounting", "ExchangeRate", ["view", "add"]),
        _perms("sales", "SaleInvoice", ["view"]),
        _perms("sales", "SaleOrder", ["view"]),
        _perms("sales", "Payment", ["view"]),
        _perms("purchasing", "PurchaseInvoice", ["view"]),
        _perms("purchasing", "PurchaseOrder", ["view"]),
        _perms("purchasing", "PurchasePayment", ["view"]),
        _perms("inventory", "Inventory", ["view"]),
        _perms("configuration", "Currency", ["view"]),
        _perms("configuration", "Company", ["view"]),
    )
    print(f"   ✅ Grupo 'Contabilidad' → {contab.permissions.count()} permisos")

    # --------------------------------------------------------
    # RRHH
    # --------------------------------------------------------
    rrhh, _ = Group.objects.get_or_create(name="RRHH")
    rrhh.permissions.clear()
    _add_perms(
        rrhh,
        _perms("rrhh", "Employee", ["view", "add", "change"]),
        _perms("rrhh", "Commission", ["view", "change"]),
        _custom_perm("rrhh", "Commission", "can_pay_commission"),
        _perms("users", "User", ["view"]),
        _perms("configuration", "Company", ["view"]),
        _perms("sales", "SaleInvoice", ["view"]),
        _perms("sales", "SaleOrder", ["view"]),
    )
    print(f"   ✅ Grupo 'RRHH' → {rrhh.permissions.count()} permisos")

    # --------------------------------------------------------
    # ADMINISTRADORES (sin auth/users/company/backup)
    # --------------------------------------------------------
    admin_grp, _ = Group.objects.get_or_create(name="Administradores")
    admin_grp.permissions.clear()

    full_access_apps = ["sales", "purchasing", "inventory", "accounting"]
    skip_models = ["historical", "historicalsaleinvoice", "historicalsaleorder",
                   "historicalpurchaseline", "historicalpurchaseorder",
                   "historicalmovement", "historicalinventory", "commission",
                   "employee"]

    for app_label in full_access_apps:
        for ct in ContentType.objects.filter(app_label=app_label):
            if any(skip in ct.model.lower() for skip in skip_models):
                continue
            admin_grp.permissions.add(*_perms(app_label, ct.model, ["view", "add", "change"]))

    _add_perms(
        admin_grp,
        _perms("rrhh", "Commission", ["view", "change"]),
        _custom_perm("rrhh", "Commission", "can_pay_commission"),
        _perms("rrhh", "Employee", ["view", "change"]),
        _perms("configuration", "Currency", ["view"]),
        _perms("configuration", "PaymentMethod", ["view"]),
        _perms("configuration", "CompanyBankAccount", ["view"]),
        _perms("users", "User", ["view"]),
    )
    print(f"   ✅ Grupo 'Administradores' → {admin_grp.permissions.count()} permisos")

    # --------------------------------------------------------
    # VENTAS SUPERVISOR
    # --------------------------------------------------------
    ventas_sup, _ = Group.objects.get_or_create(name="Ventas Supervisor")
    ventas_sup.permissions.clear()
    ventas_sup.permissions.add(*ventas.permissions.all())
    _add_perms(
        ventas_sup,
        _perms("sales", "SaleOrder", ["delete"]),
        _perms("sales", "SaleInvoice", ["delete"]),
        _custom_perm("sales", "SaleOrder", "can_cancel_order"),
        _custom_perm("sales", "SaleOrder", "can_view_reports"),
        _perms("configuration", "Company", ["view"]),
    )
    print(f"   ✅ Grupo 'Ventas Supervisor' → {ventas_sup.permissions.count()} permisos")

    # --------------------------------------------------------
    # ALMACÉN SUPERVISOR
    # --------------------------------------------------------
    almacen_sup, _ = Group.objects.get_or_create(name="Almacén Supervisor")
    almacen_sup.permissions.clear()
    almacen_sup.permissions.add(*almacen.permissions.all())
    _add_perms(
        almacen_sup,
        _perms("inventory", "PhysicalCount", ["delete"]),
        _custom_perm("inventory", "DeliveryNote", "can_cancel_deliverynote"),
        _custom_perm("inventory", "ReceiptNote", "can_cancel_receiptnote"),
    )
    print(f"   ✅ Grupo 'Almacén Supervisor' → {almacen_sup.permissions.count()} permisos")


# ============================================================
# MAIN
# ============================================================
@transaction.atomic
def load_all():
    print("=" * 70)
    print("📥 CARGANDO DATOS BÁSICOS DE PRODUCCIÓN")
    print("=" * 70)

    load_currencies()
    company = load_company()
    load_exchange_rates(company)
    load_taxes()
    load_tax_rates(company)
    load_payment_methods(company)
    load_locations(company)
    load_groups()

    print("\n" + "=" * 70)
    print("✅ CARGA COMPLETADA EXITOSAMENTE")
    print("=" * 70)
    print("\n📌 Próximos pasos:")
    print("   1. Entra al admin: /admin/")
    print("   2. Verifica la empresa en: Configuración → Empresa")
    print("   3. Revisa los grupos en: Configuración → Grupos")
    print("   4. Revisa la tasa de cambio en: Contabilidad → Tasa de Cambio")
    print("   5. Crea productos, clientes y proveedores")
    print("   6. Asigna usuarios a los grupos correspondientes")
    print()


if __name__ == "__main__":
    load_all()