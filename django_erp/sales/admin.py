# sales/admin.py - VERSIÓN CON FORZADO DE CONFIRMACIÓN
from django.contrib import admin
from django import forms
from django.utils.html import format_html
from django.urls import reverse
from django.apps import apps
from django.contrib import messages
from django.core.exceptions import ValidationError
from unfold.admin import ModelAdmin as UnfoldModelAdmin
from unfold.admin import TabularInline as UnfoldTabularInline
from .models import Customer, SaleOrder, SaleLine
from .models import CashRegister, CashTransaction
from .helpers import get_open_register
from decimal import Decimal, ROUND_HALF_UP
from django.utils import timezone


@admin.register(Customer)
class CustomerAdmin(UnfoldModelAdmin):
    list_display = ['name', 'tax_id', 'email', 'phone', 'is_active']
    list_filter = ['is_active']
    search_fields = ['name', 'tax_id', 'email', 'phone']
    
    fieldsets = (
        ('Información', {
            'fields': ('name', 'tax_id', 'email', 'phone', 'address')
        }),
        ('Estado', {
            'fields': ('is_active',)
        }),
    )
    readonly_fields = ['created_at', 'updated_at']


class SaleLineInline(UnfoldTabularInline):
    model = SaleLine
    extra = 0
    fields = ['product', 'location', 'quantity', 'unit_price', 'subtotal']
    readonly_fields = ['subtotal']
    autocomplete_fields = ['product']
    
    def get_formset(self, request, obj=None, **kwargs):
        formset = super().get_formset(request, obj, **kwargs)
        from django_erp.warehouse.models import Product, Location
        formset.form.base_fields['product'].queryset = Product.objects.filter(is_active=True)
        formset.form.base_fields['location'].queryset = Location.objects.filter(is_active=True)
        formset.form.base_fields['unit_price'].initial = 0
        formset.form.base_fields['quantity'].initial = 1
        return formset


class SaleOrderForm(forms.ModelForm):
    # ✅ Estos campos son solo para mostrar, no se guardan
    subtotal_display = forms.CharField(
        required=False,
        disabled=True,
        label="Subtotal (USD)",
        initial="0.00"
    )
    
    subtotal_bs_display = forms.CharField(
        required=False,
        disabled=True,
        label="Subtotal (Bs.)",
        initial="0.00"
    )
    
    tax_display = forms.CharField(
        required=False,
        disabled=True,
        label="IVA (USD)",
        initial="0.00"
    )
    
    tax_bs_display = forms.CharField(
        required=False,
        disabled=True,
        label="IVA (Bs.)",
        initial="0.00"
    )
    
    total_display = forms.CharField(
        required=False,
        disabled=True,
        label="Total (USD)",
        initial="0.00"
    )
    
    total_bs_display = forms.CharField(
        required=False,
        disabled=True,
        label="Total (Bs.)",
        initial="0.00",
        help_text="Convertido según tasa del día"
    )
    
    rate_display = forms.CharField(
        required=False,
        disabled=True,
        label="Tasa del día",
        initial="1 USD = Bs. 0.00"
    )
    
    class Meta:
        model = SaleOrder
        fields = ['number', 'customer', 'status', 'note']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        instance = kwargs.get('instance')
        
        from django_erp.configuration.models import ExchangeRate
        rate = ExchangeRate.get_today_rate('USD', 'BS')
        if rate:
            self.initial['rate_display'] = f"1 USD = Bs. {rate:.2f}"
        else:
            self.initial['rate_display'] = "No hay tasa configurada"
        
        if instance and instance.pk:
            # ✅ Calcular totales desde las líneas
            subtotal = sum(line.subtotal for line in instance.lines.all())
            tax_rate = Decimal('19')
            tax = subtotal * (tax_rate / Decimal('100'))
            total = subtotal + tax
            
            self.initial['subtotal_display'] = f"{subtotal:.2f}"
            self.initial['tax_display'] = f"{tax:.2f}"
            self.initial['total_display'] = f"{total:.2f}"
            
            if rate:
                self.initial['subtotal_bs_display'] = f"{(subtotal * rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP):.2f}"
                self.initial['tax_bs_display'] = f"{(tax * rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP):.2f}"
                self.initial['total_bs_display'] = f"{(total * rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP):.2f}"
        else:
            self.initial['subtotal_display'] = "0.00"
            self.initial['tax_display'] = "0.00"
            self.initial['total_display'] = "0.00"
            self.initial['subtotal_bs_display'] = "0.00"
            self.initial['tax_bs_display'] = "0.00"
            self.initial['total_bs_display'] = "0.00"
        
        if not instance or not instance.pk:
            from datetime import datetime
            last_order = SaleOrder.objects.order_by('-id').first()
            if last_order and last_order.number:
                try:
                    last_num = int(last_order.number.split('-')[-1])
                    next_num = last_num + 1
                except (ValueError, IndexError):
                    next_num = 1
            else:
                next_num = 1
            
            self.initial['number'] = f"VENTA-{datetime.now().strftime('%Y%m%d')}-{next_num:04d}"
            self.fields['number'].disabled = True
            self.initial['status'] = 'DRAFT'
            self.fields['status'].choices = [
                ('DRAFT', 'Borrador'),
            ]
        else:
            if instance.status == 'DRAFT':
                self.fields['status'].choices = [
                    ('DRAFT', 'Borrador'),
                    ('CONFIRMED', 'Confirmada'),
                ]
            elif instance.status == 'CONFIRMED':
                self.fields['status'].choices = [
                    ('CONFIRMED', 'Confirmada'),
                    ('DELIVERED', 'Entregada'),
                    ('CANCELLED', 'Cancelada'),
                ]
            elif instance.status == 'DELIVERED':
                self.fields['status'].choices = [
                    ('DELIVERED', 'Entregada'),
                ]
            elif instance.status == 'CANCELLED':
                self.fields['status'].choices = [
                    ('CANCELLED', 'Cancelada'),
                ]


@admin.action(description='🔄 Reconfirmar orden (forzar reducción de stock)')
def reconfirm_order_action(modeladmin, request, queryset):
    """Acción para reconfirmar órdenes y forzar reducción de stock"""
    from .services import SaleService
    from .signals import order_confirmed
    
    for order in queryset:
        try:
            print(f"🔴 Reconfirmando orden {order.number}")
            
            # ✅ Verificar caja abierta
            try:
                get_open_register(request.user)
            except ValidationError as e:
                modeladmin.message_user(request, f"Error con {order.number}: {str(e)}", messages.ERROR)
                continue
            
            # ✅ Verificar que tenga líneas
            if not order.lines.exists():
                modeladmin.message_user(request, f"La orden {order.number} no tiene líneas.", messages.WARNING)
                continue
            
            # ✅ Reducir stock manualmente
            for line in order.lines.all():
                if line.product and not line.product.is_service:
                    print(f"   Reduciendo stock de {line.product.name} x {line.quantity}")
                    try:
                        from django_erp.warehouse.services import WarehouseService
                        WarehouseService.create_exit(
                            product_id=line.product.id,
                            quantity=line.quantity,
                            location_from_id=line.location.id if line.location else None,
                            unit_price=line.unit_price,
                            source_type='SALE',
                            source_reference=order.number,
                            note=f"Venta {order.number} - Reconfirmación",
                            user=request.user
                        )
                        print(f"   ✅ Stock reducido para {line.product.name}")
                    except Exception as e:
                        print(f"   ❌ Error al reducir stock: {e}")
                        modeladmin.message_user(request, f"Error con {order.number}: {e}", messages.ERROR)
                        continue
            
            # ✅ Registrar en caja si no existe transacción
            existing = CashTransaction.objects.filter(
                reference=order.number,
                type='SALE'
            ).exists()
            
            if not existing:
                print(f"   Registrando en caja...")
                order._status_changed_by = request.user
                order_confirmed.send(sender=SaleOrder, order=order)
                print(f"   ✅ Registro en caja completado")
            else:
                print(f"   ⚠️ La transacción ya existe para {order.number}")
            
            modeladmin.message_user(request, f'✅ Orden {order.number} reconfirmada exitosamente', messages.SUCCESS)
            
        except Exception as e:
            print(f"❌ Error al reconfirmar {order.number}: {e}")
            modeladmin.message_user(request, f"Error con {order.number}: {e}", messages.ERROR)


@admin.register(SaleOrder)
class SaleOrderAdmin(UnfoldModelAdmin):
    form = SaleOrderForm
    
    list_display = ['number', 'customer', 'date', 'total', 'status', 'created_at']
    list_filter = ['status', 'date']
    search_fields = ['number', 'customer__name']
    
    inlines = [SaleLineInline]
    
    autocomplete_fields = ['customer']
    actions = [reconfirm_order_action]
    
    fieldsets = (
        ('Información de la Orden', {
            'fields': ('number', 'customer', 'status')
        }),
        ('Totales en Tiempo Real', {
            'fields': (
                ('subtotal_display', 'subtotal_bs_display'),
                ('tax_display', 'tax_bs_display'),
                ('total_display', 'total_bs_display'),
                'rate_display',
            ),
            'classes': ('tab', 'wide'),
            'description': 'Los totales se actualizan automáticamente al modificar las líneas'
        }),
        ('Información Adicional', {
            'fields': ('note',),
            'classes': ('tab',),
        }),
    )
    
    readonly_fields = ['user', 'date', 'created_at', 'updated_at']
    
    class Media:
        js = ('admin/js/sale_order_admin.js',)
    
    def save_model(self, request, obj, form, change):
        """Guardar la orden (sin calcular totales aquí)"""
        if not obj.user:
            obj.user = request.user
        
        obj._status_changed_by = request.user
        
        # ✅ Guardar el objeto (los totales se calculan en save_formset)
        super().save_model(request, obj, form, change)
    
    def save_formset(self, request, form, formset, change):
        """Guardar líneas, calcular totales y procesar confirmación"""
        from .services import SaleService
        from .signals import order_confirmed
        
        # ✅ 1. Guardar las líneas
        super().save_formset(request, form, formset, change)
        
        # ✅ 2. Calcular totales desde las líneas
        obj = form.instance
        subtotal = sum(line.subtotal for line in obj.lines.all())
        tax_rate = Decimal('19')
        tax = subtotal * (tax_rate / Decimal('100'))
        total = subtotal + tax
        
        obj.subtotal = subtotal
        obj.tax = tax
        obj.total = total
        
        # ✅ 3. Guardar la orden con los totales
        obj.save()
        
        print(f"🔴 Totales calculados para {obj.number}:")
        print(f"   Subtotal: {subtotal}")
        print(f"   IVA: {tax}")
        print(f"   Total: {total}")
        
        # ✅ 4. Verificar si el estado es CONFIRMED
        new_status = form.cleaned_data.get('status')
        
        print(f"   Nuevo estado: {new_status}")
        
        # ✅ 5. PROCESAR SIEMPRE QUE EL ESTADO SEA CONFIRMED
        if new_status == 'CONFIRMED':
            print(f"🔴 PROCESANDO CONFIRMACIÓN para {obj.number}")
            
            # ✅ Verificar si la orden ya fue procesada (tiene movimiento)
            from django_erp.warehouse.models import Movement
            has_movement = Movement.objects.filter(
                source_reference=obj.number,
                source_type='SALE'
            ).exists()
            
            if has_movement:
                print(f"   ⚠️ La orden {obj.number} ya fue procesada anteriormente (tiene movimientos).")
                print(f"   ℹ️ No se procesa nuevamente para evitar duplicados.")
                
                # ✅ Verificar si tiene transacción en caja
                from .models import CashTransaction
                has_transaction = CashTransaction.objects.filter(
                    reference=obj.number,
                    type='SALE'
                ).exists()
                
                if not has_transaction and obj.total > 0:
                    print(f"   🔴 La orden tiene movimientos pero no transacción en caja. Registrando...")
                    obj._status_changed_by = request.user
                    order_confirmed.send(sender=SaleOrder, order=obj)
                    self.message_user(request, f'✅ Transacción en caja registrada para {obj.number}', messages.SUCCESS)
                
                # ✅ Reubicar líneas si es necesario
                for line in obj.lines.all():
                    if line.product and not line.location:
                        from django_erp.inventory.models import Inventory
                        inventory = Inventory.objects.filter(product=line.product).first()
                        if inventory and inventory.location:
                            line.location = inventory.location
                            line.save()
                return
            
            # ✅ Verificar caja abierta
            try:
                get_open_register(request.user)
            except ValidationError as e:
                self.message_user(request, str(e), messages.ERROR)
                return
            
            # ✅ PROCESAR CONFIRMACIÓN
            print(f"   ✅ Procesando confirmación por primera vez...")
            
            # ✅ Cambiar el estado a CONFIRMED
            obj.status = 'CONFIRMED'
            obj.save()
            print(f"   ✅ Estado cambiado a CONFIRMED")
            
            # ✅ Confirmar la orden (esto reduce el stock y genera factura)
            print(f"   🔴 Confirmando orden (reduciendo stock)...")
            try:
                SaleService.confirm_order(obj, request.user)
                print(f"   ✅ Orden confirmada exitosamente")
            except Exception as e:
                print(f"   ❌ Error al confirmar: {e}")
                self.message_user(request, f"Error al confirmar: {e}", messages.ERROR)
                # Revertir estado
                obj.status = 'DRAFT'
                obj.save()
                return
            
            # ✅ Registrar en caja
            print(f"   🔴 Registrando en caja...")
            obj._status_changed_by = request.user
            order_confirmed.send(sender=SaleOrder, order=obj)
            print(f"   ✅ Registro en caja completado")
            
            self.message_user(request, f'✅ Orden {obj.number} confirmada exitosamente', messages.SUCCESS)
        
        # ✅ Reubicar líneas si es necesario
        for line in obj.lines.all():
            if line.product and not line.location:
                from django_erp.inventory.models import Inventory
                inventory = Inventory.objects.filter(product=line.product).first()
                if inventory and inventory.location:
                    line.location = inventory.location
                    line.save()


# ✅ ACCIONES PARA CAJA
@admin.action(description='✅ Abrir caja seleccionada')
def open_register_action(modeladmin, request, queryset):
    for register in queryset:
        if register.status == 'OPEN':
            modeladmin.message_user(request, f'La caja {register.number} ya está abierta.', messages.WARNING)
            continue
        
        if CashRegister.objects.filter(user=register.user, status='OPEN').exists():
            modeladmin.message_user(request, f'El usuario {register.user.username} ya tiene una caja abierta.', messages.ERROR)
            continue
        
        register.status = 'OPEN'
        register.opened_at = timezone.now()
        register.save()
        modeladmin.message_user(request, f'Caja {register.number} abierta exitosamente.', messages.SUCCESS)


@admin.action(description='🔒 Cerrar caja seleccionada')
def close_register_action(modeladmin, request, queryset):
    for register in queryset:
        if register.status != 'OPEN':
            modeladmin.message_user(request, f'La caja {register.number} no está abierta.', messages.WARNING)
            continue
        
        register.calculate_totals()
        
        if register.counted_total is None:
            register.counted_total = register.expected_total
            register.difference = 0
        
        register.status = 'CLOSED'
        register.closed_at = timezone.now()
        register.save()
        
        modeladmin.message_user(request, f'Caja {register.number} cerrada exitosamente. Total: {register.expected_total:.2f} USD', messages.SUCCESS)


@admin.register(CashRegister)
class CashRegisterAdmin(UnfoldModelAdmin):
    list_display = ['number', 'user', 'date', 'status_badge', 'total_sales', 'expected_total', 'counted_total', 'difference']
    list_filter = ['status', 'date']
    search_fields = ['number', 'user__username']
    actions = [open_register_action, close_register_action]
    
    fieldsets = (
        ('Información', {'fields': ('number', 'user', 'status')}),
        ('Dinero', {'fields': ('initial_amount', 'total_sales', 'total_expenses', 'total_withdrawals', 'expected_total')}),
        ('Cierre', {'fields': ('counted_total', 'breakdown', 'difference', 'note'), 'classes': ('tab',)}),
        ('Fechas', {'fields': ('opened_at', 'closed_at'), 'classes': ('tab',)}),
    )
    
    readonly_fields = ['opened_at', 'closed_at', 'total_sales', 'total_expenses', 'total_withdrawals', 'expected_total']
    
    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if obj is None:
            from datetime import datetime
            date_str = datetime.now().strftime('%Y%m%d')
            last = CashRegister.objects.filter(number__startswith=f'CAJA-{date_str}').order_by('number').last()
            next_num = int(last.number.split('-')[-1]) + 1 if last else 1
            form.base_fields['number'].initial = f'CAJA-{date_str}-{next_num:04d}'
            form.base_fields['number'].disabled = True
        return form
    
    def save_model(self, request, obj, form, change):
        if not obj.number:
            from datetime import datetime
            date_str = datetime.now().strftime('%Y%m%d')
            last = CashRegister.objects.filter(number__startswith=f'CAJA-{date_str}').order_by('number').last()
            next_num = int(last.number.split('-')[-1]) + 1 if last else 1
            obj.number = f'CAJA-{date_str}-{next_num:04d}'
        super().save_model(request, obj, form, change)
    
    @admin.display(description='Estado')
    def status_badge(self, obj):
        colors = {
            'OPEN': ('#28a745', '✅ Abierta'),
            'CLOSED': ('#17a2b8', '🔒 Cerrada'),
            'APPROVED': ('#28a745', '✅ Aprobada'),
            'CANCELLED': ('#dc3545', '❌ Cancelada'),
        }
        color, label = colors.get(obj.status, ('#6c757d', obj.status))
        return format_html(
            '<span style="background: {}; color: white; padding: 2px 10px; border-radius: 12px; font-size: 12px;">{}</span>',
            color, label
        )


@admin.register(CashTransaction)
class CashTransactionAdmin(UnfoldModelAdmin):
    list_display = ['register', 'type', 'amount', 'description', 'user', 'created_at']
    list_filter = ['type']
    search_fields = ['description', 'reference']
    readonly_fields = ['created_at']


