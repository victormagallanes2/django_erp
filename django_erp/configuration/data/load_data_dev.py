# django_erp/configuration/data/load_data_dev.py
"""
Carga de datos de PRUEBA (desarrollo):
- Clientes (globales)
- Proveedores (globales)
- Empleados (usuarios + datos de empleado, multi-sucursal)
- Productos y servicios (globales)
- Compañía sucursal (hija de la principal) con RIF heredado
- Configuración de la sucursal: tasas, métodos de pago, almacén
- Cuentas bancarias de las empresas

Uso:
    python -m django_erp.configuration.data.load_data_dev

Idempotente. Requiere que load_data_prod ya se haya ejecutado.

Para borrar todo y volver a empezar:
    python -m django_erp.configuration.data.load_data_dev --reset
"""

import os
import sys
import django
from decimal import Decimal
from datetime import date

# ============================================================
# Configuración de Django
# ============================================================
sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'django_erp.settings')
django.setup()

# ============================================================
# Imports
# ============================================================
from django.db import transaction
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import Group

from django_erp.configuration.models import (
    Company,
    Currency,
    PaymentMethod,
    CompanyBankAccount,          # ✅ NUEVO
)
from django_erp.accounting.models import ExchangeRate
from django_erp.sales.models import Customer
from django_erp.purchasing.models import Supplier
from django_erp.rrhh.models import Employee
from django_erp.inventory.models import Product, Location

User = get_user_model()


# ============================================================
# DATOS DE PRUEBA
# ============================================================

# ------------------------------------------------------------
# SUCURSAL (hija de la principal '01')
# ------------------------------------------------------------
BRANCH_COMPANY_DATA = {
    "code": "02",
    "fields": {
        "name": "Sucursal Centro",
        "trade_name": "Sucursal Centro",
        "address": "Av. Bolívar, Centro Comercial Plaza, Local 12, Valencia",
        "phone": "+58-241-555-0000",
        "email": "sucursal@company.com",
        "invoice_prefix": "SUC",
        "is_main": False,
        "is_active": True,
        "parent_code": "01",
        # ✅ NO se especifica rif: se hereda del padre
    },
}

# ------------------------------------------------------------
# CONFIGURACIÓN DE LA SUCURSAL
# ------------------------------------------------------------
BRANCH_EXCHANGE_RATES = [
    {
        "from_currency_code": "USD",
        "to_currency_code": "BS",
        "rate": Decimal("780.00"),
        "effective_date": "2026-09-02",
        "source": "BCV",
    },
]

BRANCH_LOCATIONS = [
    {
        "code": "ALM-02",
        "name": "Almacén Sucursal Centro",
        "description": "Almacén principal de la Sucursal Centro",
        "is_active": True,
    },
]

# ------------------------------------------------------------
# CUENTAS BANCARIAS DE LAS EMPRESAS
# ------------------------------------------------------------
BANK_ACCOUNTS_DATA = [
    # --- Matriz 01 ---
    {
        "company_code": "01",
        "fields": {
            "bank_name": "Banco de Venezuela",
            "account_number": "0102-0000-00-0000000000",
            "account_holder": "Compañía Default",
            "account_type": "CHECKING",
            "currency_code": "BS",
            "is_default": True,
            "is_active": True,
        },
    },
    {
        "company_code": "01",
        "fields": {
            "bank_name": "Banesco",
            "account_number": "0134-0000-00-0000000000",
            "account_holder": "Compañía Default",
            "account_type": "CHECKING",
            "currency_code": "USD",
            "is_default": False,
            "is_active": True,
        },
    },
    {
        "company_code": "01",
        "fields": {
            "bank_name": "Mercantil",
            "account_number": "0105-0000-00-0000000000",
            "account_holder": "Compañía Default",
            "account_type": "SAVINGS",
            "currency_code": "USD",
            "is_default": False,
            "is_active": True,
        },
    },
    # --- Sucursal 02 ---
    {
        "company_code": "02",
        "fields": {
            "bank_name": "Banco de Venezuela",
            "account_number": "0102-1111-11-1111111111",
            "account_holder": "Sucursal Centro",
            "account_type": "CHECKING",
            "currency_code": "BS",
            "is_default": True,
            "is_active": True,
        },
    },
    {
        "company_code": "02",
        "fields": {
            "bank_name": "Banesco",
            "account_number": "0134-1111-11-1111111111",
            "account_holder": "Sucursal Centro",
            "account_type": "CHECKING",
            "currency_code": "USD",
            "is_default": False,
            "is_active": True,
        },
    },
]

# ------------------------------------------------------------
# CLIENTES (globales, visibles en todas las sedes)
# ------------------------------------------------------------
CUSTOMERS_DATA = [
    {"company_code": "01", "fields": {
        "name": "María González", "tax_id": "V-12345678",
        "email": "maria.gonzalez@example.com", "phone": "+58-414-555-1234",
        "address": "Av. Principal, Edificio Central, Caracas", "is_active": True,
    }},
    {"company_code": "01", "fields": {
        "name": "Carlos Pérez", "tax_id": "V-87654321",
        "email": "carlos.perez@example.com", "phone": "+58-426-555-5678",
        "address": "Calle 2, Barquisimeto, Lara", "is_active": True,
    }},
    {"company_code": "01", "fields": {
        "name": "Ana Rodríguez", "tax_id": "V-34567890",
        "email": "ana.rodriguez@example.com", "phone": "+58-416-555-9012",
        "address": "Av. Libertador, Valencia, Carabobo", "is_active": True,
    }},
    {"company_code": "01", "fields": {
        "name": "John Doe", "tax_id": "V-34907890",
        "email": "john.doe@example.com", "phone": "+1-555-0199",
        "address": "Av. Los Aviadores, Maracay, Aragua", "is_active": True,
    }},
    {"company_code": "01", "fields": {
        "name": "Jane Smith", "tax_id": "V-74567890",
        "email": "jane.smith@example.com", "phone": "+1-555-0198",
        "address": "Av. Bolívar, Valencia, Carabobo", "is_active": True,
    }},
]

# ------------------------------------------------------------
# PROVEEDORES (globales, visibles en todas las sedes)
# ------------------------------------------------------------
SUPPLIERS_DATA = [
    {"company_code": "01", "fields": {
        "name": "Distribuidora Unisex C.A.", "tax_id": "J-12345678-9",
        "email": "ventas@distribuidoraunisex.com", "phone": "+58-212-555-1111",
        "address": "Av. Libertador, Edificio Unisex, Caracas", "is_active": True,
    }},
    {"company_code": "01", "fields": {
        "name": "Productos Capilares Premium", "tax_id": "J-98765432-1",
        "email": "info@capilarespremium.com", "phone": "+58-414-555-2222",
        "address": "Calle 3, Urbanización El Bosque, Caracas", "is_active": True,
    }},
    {"company_code": "01", "fields": {
        "name": "Professional Hair Supplies LLC", "tax_id": "12-3456789",
        "email": "info@prohair.com", "phone": "+1-555-0199",
        "address": "123 Main St, Suite 200, New York, NY 10001", "is_active": True,
    }},
]

# ------------------------------------------------------------
# EMPLEADOS (multi-sucursal)
# ------------------------------------------------------------
EMPLOYEES_DATA = [
    {"username": "wilmary", "fields": {
        "password": "123456", "email": "wilmary@company.com",
        "first_name": "Wilmary", "last_name": "Guerrero",
        "is_superuser": False, "is_staff": True, "is_active": True,
        "is_employee": True,
        "company_codes": ["01", "02"],
        "groups": ["Ventas"],
        "employee": {
            "position": "Peluquera",
            "commission_rate": Decimal("5.00"),
            "pin": "1001", "hire_date": "2024-01-15",
        },
    }},
    {"username": "wendy", "fields": {
        "password": "123456", "email": "wendy@company.com",
        "first_name": "Wendy", "last_name": "Guerrero",
        "is_superuser": False, "is_staff": True, "is_active": True,
        "is_employee": True,
        "company_codes": ["01", "02"],
        "groups": ["Ventas"],
        "employee": {
            "position": "Peluquera",
            "commission_rate": Decimal("5.00"),
            "pin": "1002", "hire_date": "2024-02-01",
        },
    }},
    {"username": "liz", "fields": {
        "password": "123456", "email": "liz@company.com",
        "first_name": "Liz", "last_name": "Guerrero",
        "is_superuser": False, "is_staff": True, "is_active": True,
        "is_employee": True,
        "company_codes": ["01", "02"],
        "groups": ["Ventas"],
        "employee": {
            "position": "Peluquera",
            "commission_rate": Decimal("5.00"),
            "pin": "1003", "hire_date": "2024-03-10",
        },
    }},
    {"username": "charly", "fields": {
        "password": "123456", "email": "charly@company.com",
        "first_name": "Charly", "last_name": "Mata",
        "is_superuser": False, "is_staff": True, "is_active": True,
        "is_employee": True,
        "company_codes": ["01"],
        "groups": ["Ventas"],
        "employee": {
            "position": "Peluquero",
            "commission_rate": Decimal("5.00"),
            "pin": "1004", "hire_date": "2024-04-20",
        },
    }},
]

# ------------------------------------------------------------
# PRODUCTOS Y SERVICIOS (globales)
# ------------------------------------------------------------
PRODUCTS_DATA = [
    # Productos físicos
    {"company_code": "01", "fields": {
        "code": "PROD-001", "name": "Shampoo Profesional",
        "description": "Shampoo para todo tipo de cabello",
        "unit": "UNIT", "sale_price": Decimal("15.00"),
        "purchase_price": Decimal("8.50"),
        "is_service": False, "is_active": True,
    }},
    {"company_code": "01", "fields": {
        "code": "PROD-002", "name": "Acondicionador Hidratante",
        "description": "Acondicionador con keratina",
        "unit": "UNIT", "sale_price": Decimal("12.00"),
        "purchase_price": Decimal("6.75"),
        "is_service": False, "is_active": True,
    }},
    {"company_code": "01", "fields": {
        "code": "PROD-003", "name": "Cera Modeladora",
        "description": "Cera para peinar y modelar",
        "unit": "UNIT", "sale_price": Decimal("8.00"),
        "purchase_price": Decimal("4.20"),
        "is_service": False, "is_active": True,
    }},
    {"company_code": "01", "fields": {
        "code": "PROD-004", "name": "Tinte de Cabello",
        "description": "Tinte profesional de larga duración",
        "unit": "UNIT", "sale_price": Decimal("25.00"),
        "purchase_price": Decimal("14.50"),
        "is_service": False, "is_active": True,
    }},
    {"company_code": "01", "fields": {
        "code": "PROD-005", "name": "Navaja de Afeitar",
        "description": "Navaja de afeitar profesional",
        "unit": "UNIT", "sale_price": Decimal("5.00"),
        "purchase_price": Decimal("2.30"),
        "is_service": False, "is_active": True,
    }},
    # Servicios
    {"company_code": "01", "fields": {
        "code": "SERV-001", "name": "Corte de Cabello",
        "description": "Corte de cabello para hombre y mujer",
        "unit": "UNIT", "sale_price": Decimal("10.00"),
        "purchase_price": Decimal("0.00"),
        "is_service": True, "is_active": True,
    }},
    {"company_code": "01", "fields": {
        "code": "SERV-002", "name": "Tinte y Coloración",
        "description": "Tinte profesional con productos de calidad",
        "unit": "UNIT", "sale_price": Decimal("35.00"),
        "purchase_price": Decimal("0.00"),
        "is_service": True, "is_active": True,
    }},
    {"company_code": "01", "fields": {
        "code": "SERV-003", "name": "Afeitado Clásico",
        "description": "Afeitado con navaja y toalla caliente",
        "unit": "UNIT", "sale_price": Decimal("15.00"),
        "purchase_price": Decimal("0.00"),
        "is_service": True, "is_active": True,
    }},
    # Productos adicionales
    {"company_code": "01", "fields": {
        "code": "PROD-006", "name": "Premium Shampoo",
        "description": "Professional shampoo for all hair types",
        "unit": "UNIT", "sale_price": Decimal("20.00"),
        "purchase_price": Decimal("11.50"),
        "is_service": False, "is_active": True,
    }},
    {"company_code": "01", "fields": {
        "code": "PROD-007", "name": "Hair Clay",
        "description": "Matte hair clay for styling",
        "unit": "UNIT", "sale_price": Decimal("12.00"),
        "purchase_price": Decimal("6.80"),
        "is_service": False, "is_active": True,
    }},
    # Servicios adicionales
    {"company_code": "01", "fields": {
        "code": "SERV-004", "name": "Haircut",
        "description": "Professional haircut for men and women",
        "unit": "UNIT", "sale_price": Decimal("30.00"),
        "purchase_price": Decimal("0.00"),
        "is_service": True, "is_active": True,
    }},
    {"company_code": "01", "fields": {
        "code": "SERV-005", "name": "Beard Trim",
        "description": "Professional beard trimming and shaping",
        "unit": "UNIT", "sale_price": Decimal("15.00"),
        "purchase_price": Decimal("0.00"),
        "is_service": True, "is_active": True,
    }},
]


# ============================================================
# HELPERS
# ============================================================
def get_company(code="01"):
    try:
        return Company.objects.get(code=code)
    except Company.DoesNotExist:
        raise RuntimeError(
            f"❌ La empresa '{code}' no existe. "
            f"Corre primero: python -m django_erp.configuration.data.load_data_prod"
        )


def get_admin_user():
    user = User.objects.filter(username="admin").first()
    if user:
        return user
    return User.objects.filter(is_superuser=True).first()


# ============================================================
# 1. CLIENTES
# ============================================================
def load_customers(company):
    print("\n👤 Cargando clientes...")
    created = updated = 0

    for item in CUSTOMERS_DATA:
        fields = item["fields"].copy()
        tax_id = fields.pop("tax_id", None)
        if not tax_id:
            continue

        customer, was_created = Customer.objects.update_or_create(
            tax_id=tax_id,
            defaults={**fields, "created_in_company": company},
        )

        if was_created:
            created += 1
            print(f"   ✅ Cliente creado: {customer.name} ({customer.tax_id})")
        else:
            updated += 1
            print(f"   ℹ️ Cliente actualizado: {customer.name} ({customer.tax_id})")

    print(f"   📊 Total: {created} creados, {updated} actualizados")


# ============================================================
# 2. PROVEEDORES
# ============================================================
def load_suppliers(company):
    print("\n🏭 Cargando proveedores...")
    created = updated = 0

    for item in SUPPLIERS_DATA:
        fields = item["fields"].copy()
        tax_id = fields.pop("tax_id", None)
        if not tax_id:
            continue

        supplier, was_created = Supplier.objects.update_or_create(
            tax_id=tax_id,
            defaults={**fields, "created_in_company": company},
        )

        if was_created:
            created += 1
            print(f"   ✅ Proveedor creado: {supplier.name} ({supplier.tax_id})")
        else:
            updated += 1
            print(f"   ℹ️ Proveedor actualizado: {supplier.name} ({supplier.tax_id})")

    print(f"   📊 Total: {created} creados, {updated} actualizados")


# ============================================================
# 3. EMPLEADOS
# ============================================================
def load_employees(companies_by_code):
    print("\n👥 Cargando empleados...")
    created = updated = 0

    for item in EMPLOYEES_DATA:
        username = item["username"]
        fields = item["fields"].copy()

        company_codes = fields.pop("company_codes", [])
        group_names = fields.pop("groups", [])
        employee_data = fields.pop("employee", {})
        raw_password = fields.pop("password", None)

        if raw_password and not raw_password.startswith("pbkdf2_"):
            fields["password"] = make_password(raw_password)

        user, was_created = User.objects.update_or_create(
            username=username, defaults=fields,
        )

        # Sincronizar compañías
        expected_companies = [
            companies_by_code[c] for c in company_codes
            if c in companies_by_code
        ]
        user.companies.set(expected_companies)

        # Grupos
        for group_name in group_names:
            try:
                user.groups.add(Group.objects.get(name=group_name))
            except Group.DoesNotExist:
                print(f"   ⚠️ Grupo '{group_name}' no existe")

        # Empleado
        if user.is_employee:
            Employee.objects.update_or_create(
                user=user,
                defaults={
                    "position": employee_data.get("position", ""),
                    "commission_rate": employee_data.get(
                        "commission_rate", Decimal("5.00")
                    ),
                    "pin": employee_data.get("pin") or None,
                    "hire_date": employee_data.get("hire_date"),
                },
            )

        sede_text = ", ".join(company_codes)
        if was_created:
            created += 1
            print(f"   ✅ Empleado creado: {user.get_full_name()} "
                  f"({username}) → sedes: {sede_text}")
        else:
            updated += 1
            print(f"   ℹ️ Empleado actualizado: {user.get_full_name()} "
                  f"({username}) → sedes: {sede_text}")

    print(f"   📊 Total: {created} creados, {updated} actualizados")


# ============================================================
# 4. PRODUCTOS
# ============================================================
def load_products(company):
    print("\n📦 Cargando productos y servicios...")
    created = updated = 0
    productos = servicios = 0

    for item in PRODUCTS_DATA:
        fields = item["fields"].copy()
        code = fields.pop("code", None)
        if not code:
            continue

        # ✅ Product es global: no se asigna company
        product, was_created = Product.objects.update_or_create(
            code=code,
            defaults=fields,
        )

        tipo = "Servicio" if product.is_service else "Producto"
        if product.is_service:
            servicios += 1
        else:
            productos += 1

        if was_created:
            created += 1
            print(f"   ✅ {tipo} creado: {product.code} - {product.name} "
                  f"(${product.sale_price})")
        else:
            updated += 1
            print(f"   ℹ️ {tipo} actualizado: {product.code} - {product.name} "
                  f"(${product.sale_price})")

    print(f"   📊 Total: {created} creados, {updated} actualizados "
          f"({productos} productos, {servicios} servicios)")


# ============================================================
# 5. SUCURSAL
# ============================================================
def load_branch_company(main_company):
    """Crea/actualiza la sucursal como hija de la compañía principal."""
    print("\n🏬 Cargando compañía sucursal...")

    code = BRANCH_COMPANY_DATA["code"]
    fields = BRANCH_COMPANY_DATA["fields"].copy()
    fields.pop("parent_code", None)

    fields["parent"] = main_company
    fields["rif"] = main_company.rif
    fields["default_currency"] = main_company.default_currency

    branch, created = Company.objects.update_or_create(
        code=code,
        defaults=fields,
    )

    if created:
        print(f"   ✅ Sucursal creada: {branch.code} - {branch.name}")
    else:
        print(f"   ℹ️ Sucursal actualizada: {branch.code} - {branch.name}")

    print(f"   📌 Padre: {branch.parent.code} - {branch.parent.name}")
    print(f"   📌 RIF heredado: {branch.rif}")

    admin = get_admin_user()
    if admin and hasattr(admin, "companies"):
        admin.companies.add(branch)
        print(f"   ✅ Admin '{admin.username}' asignado a la sucursal")

    return branch


def load_branch_exchange_rates(branch):
    """Copia las tasas de cambio a la sucursal."""
    print("\n💵 Cargando tasas de cambio de la sucursal...")

    admin = get_admin_user()
    today = date.today()

    for item in BRANCH_EXCHANGE_RATES:
        try:
            from_currency = Currency.objects.get(code=item["from_currency_code"])
            to_currency = Currency.objects.get(code=item["to_currency_code"])
        except Currency.DoesNotExist as e:
            print(f"   ❌ Moneda no encontrada: {e}")
            continue

        effective_date = date.fromisoformat(item["effective_date"])

        existing = ExchangeRate.objects.filter(
            company=branch,
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
                company=branch,
                date=today,
            )
            print(f"   ✅ Tasa creada: 1 {from_currency.code} = "
                  f"{rate.rate} {to_currency.code} ({effective_date})")


def load_branch_payment_methods(branch):
    """Crea métodos de pago para la sucursal copiando los de la principal."""
    print("\n💳 Cargando métodos de pago de la sucursal...")

    from django_erp.configuration.data.load_data_prod import PAYMENT_METHODS_DATA

    created = updated = 0
    for item in PAYMENT_METHODS_DATA:
        code = item["code"]
        fields = {k: v for k, v in item.items() if k != "code"}

        default_currency_code = fields.pop("default_currency_code", None)
        default_currency = None
        if default_currency_code:
            try:
                default_currency = Currency.objects.get(code=default_currency_code)
            except Currency.DoesNotExist:
                pass

        method, was_created = PaymentMethod.objects.update_or_create(
            code=code,
            company=branch,
            defaults={**fields, "default_currency": default_currency},
        )
        if was_created:
            created += 1
            print(f"   ✅ Método creado: {method.code} - {method.name}")
        else:
            updated += 1
            print(f"   ℹ️ Método actualizado: {method.code} - {method.name}")

    print(f"   📊 Total: {created} creados, {updated} actualizados")


def load_branch_locations(branch):
    """Crea las ubicaciones (almacenes) de la sucursal."""
    print("\n📍 Cargando ubicaciones de la sucursal...")

    created = updated = 0
    for item in BRANCH_LOCATIONS:
        code = item["code"]
        fields = {k: v for k, v in item.items() if k != "code"}

        location, was_created = Location.objects.update_or_create(
            code=code,
            company=branch,
            defaults=fields,
        )
        if was_created:
            created += 1
            print(f"   ✅ Ubicación creada: {location.code} - {location.name}")
        else:
            updated += 1
            print(f"   ℹ️ Ubicación actualizada: {location.code} - {location.name}")

    print(f"   📊 Total: {created} creadas, {updated} actualizadas")


# ============================================================
# 6. CUENTAS BANCARIAS
# ============================================================
def load_company_bank_accounts(companies_by_code):
    """
    Carga las cuentas bancarias de las empresas.
    La moneda (currency) es un FK obligatorio, así que se resuelve
    por código (BS, USD, etc.) en runtime.
    """
    print("\n🏦 Cargando cuentas bancarias...")
    created = updated = 0

    for item in BANK_ACCOUNTS_DATA:
        company_code = item["company_code"]
        fields = item["fields"].copy()

        company = companies_by_code.get(company_code)
        if not company:
            print(f"   ⚠️ Empresa '{company_code}' no encontrada, saltando")
            continue

        # Resolver moneda
        currency_code = fields.pop("currency_code", None)
        if not currency_code:
            print(f"   ⚠️ Cuenta sin currency_code, saltando")
            continue

        try:
            currency = Currency.objects.get(code=currency_code)
        except Currency.DoesNotExist:
            print(f"   ⚠️ Moneda '{currency_code}' no encontrada, saltando")
            continue

        # Clave natural: company + bank_name + account_number
        bank_name = fields.get("bank_name")
        account_number = fields.get("account_number")

        account, was_created = CompanyBankAccount.objects.update_or_create(
            company=company,
            bank_name=bank_name,
            account_number=account_number,
            defaults={
                **fields,
                "currency": currency,
            },
        )

        if was_created:
            created += 1
            print(f"   ✅ Cuenta creada: [{company_code}] {account.bank_name} "
                  f"- {account.account_number} ({currency.code})")
        else:
            updated += 1
            print(f"   ℹ️ Cuenta actualizada: [{company_code}] {account.bank_name} "
                  f"- {account.account_number} ({currency.code})")

    print(f"   📊 Total: {created} creadas, {updated} actualizadas")


# ============================================================
# RESET
# ============================================================
@transaction.atomic
def reset_dev_data():
    print("=" * 70)
    print("🧹 BORRANDO DATOS DE PRUEBA")
    print("=" * 70)

    # 1. Cuentas bancarias (primero, tienen FK a Company)
    bank_account_keys = [
        (item["fields"]["bank_name"], item["fields"]["account_number"])
        for item in BANK_ACCOUNTS_DATA
    ]
    deleted_count = 0
    for bank_name, account_number in bank_account_keys:
        deleted = CompanyBankAccount.objects.filter(
            bank_name=bank_name,
            account_number=account_number,
        ).delete()
        deleted_count += deleted[0]
    print(f"   🗑️ Cuentas bancarias borradas: {deleted_count}")

    # 2. Productos
    codes = [item["fields"]["code"] for item in PRODUCTS_DATA]
    deleted = Product.objects.filter(code__in=codes).delete()
    print(f"   🗑️ Productos borrados: {deleted[0]}")

    # 3. Clientes
    tax_ids = [item["fields"]["tax_id"] for item in CUSTOMERS_DATA]
    deleted = Customer.objects.filter(tax_id__in=tax_ids).delete()
    print(f"   🗑️ Clientes borrados: {deleted[0]}")

    # 4. Proveedores
    tax_ids = [item["fields"]["tax_id"] for item in SUPPLIERS_DATA]
    deleted = Supplier.objects.filter(tax_id__in=tax_ids).delete()
    print(f"   🗑️ Proveedores borrados: {deleted[0]}")

    # 5. Empleados (usuarios)
    usernames = [item["username"] for item in EMPLOYEES_DATA]
    deleted = User.objects.filter(username__in=usernames).delete()
    print(f"   🗑️ Usuarios borrados: {deleted[0]}")

    # 6. Sucursal (al final, después de quitarle dependencias)
    branch_code = BRANCH_COMPANY_DATA["code"]
    deleted = Company.objects.filter(code=branch_code).delete()
    print(f"   🗑️ Sucursal borrada: {deleted[0]}")

    print("\n✅ Datos de prueba eliminados")


# ============================================================
# MAIN
# ============================================================
@transaction.atomic
def load_all():
    print("=" * 70)
    print("📥 CARGANDO DATOS DE PRUEBA (DESARROLLO)")
    print("=" * 70)

    # 1. Compañía principal
    company = get_company("01")
    companies_by_code = {"01": company}

    # 2. Sucursal (hija)
    branch = load_branch_company(company)
    companies_by_code["02"] = branch

    # 3. Configuración de la sucursal
    load_branch_exchange_rates(branch)
    load_branch_payment_methods(branch)
    load_branch_locations(branch)

    # 4. Cuentas bancarias
    load_company_bank_accounts(companies_by_code)

    # 5. Datos globales
    load_customers(company)
    load_suppliers(company)
    load_employees(companies_by_code)
    load_products(company)

    print("\n" + "=" * 70)
    print("✅ CARGA COMPLETADA")
    print("=" * 70)

    # ============================================================
    # RESUMEN
    # ============================================================
    print("\n📌 Compañías:")
    print(f"   01 - {company.name}  (Principal)  RIF: {company.rif}")
    print(f"   02 - {branch.name}  (Sucursal)   RIF: {branch.rif}")

    print("\n📌 Credenciales de prueba:")
    print("   Usuario         Contraseña   PIN    Sedes")
    print("   ─────────────   ──────────   ────   ─────")
    for item in EMPLOYEES_DATA:
        emp = item["fields"].get("employee", {})
        pin = emp.get("pin", "—")
        sedes = ", ".join(item["fields"]["company_codes"])
        print(f"   {item['username']:<15} 123456       {pin:<6} {sedes}")

    print("\n📌 Almacenes:")
    for loc in Location.objects.filter(
        company__in=[company, branch]
    ).order_by('company__code'):
        print(f"   [{loc.company.code}] {loc.code} - {loc.name}")

    print("\n📌 Cuentas bancarias:")
    for acc in CompanyBankAccount.objects.filter(
        company__in=[company, branch]
    ).order_by('company__code', '-is_default'):
        star = "⭐" if acc.is_default else "  "
        print(f"   [{acc.company.code}] {star} {acc.bank_name} - "
              f"{acc.account_number} ({acc.currency.code})")

    print()


if __name__ == "__main__":
    if "--reset" in sys.argv:
        reset_dev_data()
    else:
        load_all()