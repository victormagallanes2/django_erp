from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from decimal import Decimal
from .models import Inventory, PhysicalCount, Product, Location, Movement
from django_erp.configuration.models import Company
import logging


logger = logging.getLogger(__name__)


# ============================================================
# SERVICIOS DE ALMACÉN (ANTIGUO WAREHOUSE)
# ============================================================

class WarehouseService:
    """Servicios de gestión física del almacén"""

    @staticmethod
    def get_or_create_default_location(company):
        """Obtener o crear una ubicación por defecto para la compañía"""
        if not company:
            return None
        
        default_location = Location.objects.filter(
            company=company,
            is_active=True
        ).first()
        
        if not default_location:
            default_location = Location.objects.create(
                code=f"ALM-{company.code}",
                name=f"Almacén Principal - {company.name}",
                description=f"Almacén principal de {company.name}",
                company=company,
                is_active=True
            )
            logger.info(f"✅ Creada ubicación por defecto para {company.code}: {default_location.code}")
        
        return default_location

    @staticmethod
    @transaction.atomic
    def create_entry(product_id, quantity, location_to_id, source_type='MANUAL', 
                     source_reference='', note='', user=None, unit_price=0, company=None):
        """Registrar entrada de mercancía a una ubicación"""
        
        logger.info("=" * 80)
        logger.info("🔴 [create_entry] INICIANDO CREACIÓN DE ENTRADA")
        logger.info(f"   product_id: {product_id}")
        logger.info(f"   quantity: {quantity}")
        logger.info(f"   location_to_id: {location_to_id}")
        logger.info(f"   source_type: {source_type}")
        logger.info(f"   source_reference: {source_reference}")
        
        if company is None:
            company = Company.get_active()
            if not company:
                logger.error("❌ [create_entry] No hay una compañía activa")
                raise ValidationError("No hay una compañía activa para este movimiento.")
            logger.warning(f"⚠️ [create_entry] No se pasó compañía, usando fallback: {company.code}")
        
        try:
            product = Product.objects.get(id=product_id)
            logger.info(f"   ✅ Producto encontrado: {product.code} - {product.name}")
        except Product.DoesNotExist as e:
            logger.error(f"❌ [create_entry] Producto no encontrado: {e}")
            raise
        
        try:
            location_to = Location.objects.get(id=location_to_id)
            logger.info(f"   ✅ Ubicación encontrada: {location_to.code} - {location_to.name}")
        except Location.DoesNotExist as e:
            logger.error(f"❌ [create_entry] Ubicación no encontrada: {e}")
            raise
        
        if quantity <= 0:
            logger.error(f"❌ [create_entry] Cantidad inválida: {quantity}")
            raise ValidationError("La cantidad debe ser mayor a cero")
        
        logger.info("   📝 Creando movimiento...")
        movement = Movement.objects.create(
            product=product,
            type='ENTRY',
            quantity=quantity,
            unit_price=unit_price,
            location_to=location_to,
            source_type=source_type,
            source_reference=source_reference,
            note=note,
            user=user,
            company=company,
        )
        
        logger.info(f"   ✅ Movimiento creado: ID {movement.id}")
        
        # ✅ ACTUALIZACIÓN DIRECTA DEL INVENTARIO (no depende de señales)
        logger.info("   🔄 Actualizando inventario directamente...")
        try:
            InventoryService.update_stock_from_movement(movement)
            logger.info("   ✅ Inventario actualizado correctamente")
        except Exception as e:
            logger.error(f"   ❌ ERROR actualizando inventario: {e}")
            import traceback
            logger.error(f"   Traceback: {traceback.format_exc()}")
            raise  # Re-lanzar para que la transacción se revierta
        
        logger.info("🔴 [create_entry] FINALIZADO EXITOSAMENTE")
        logger.info("=" * 80)
        return movement
    
    @staticmethod
    @transaction.atomic
    def create_exit(product_id, quantity, location_from_id, source_type='MANUAL', 
                    source_reference='', note='', user=None, unit_price=0, company=None):
        """Registrar salida de mercancía desde una ubicación"""
        
        logger.info("=" * 80)
        logger.info("🔴 [create_exit] INICIANDO CREACIÓN DE SALIDA")
        logger.info(f"   product_id: {product_id}")
        logger.info(f"   quantity: {quantity}")
        logger.info(f"   location_from_id: {location_from_id}")
        logger.info(f"   source_type: {source_type}")
        logger.info(f"   source_reference: {source_reference}")
        
        if company is None:
            company = Company.get_active()
            if not company:
                logger.error("❌ [create_exit] No hay una compañía activa")
                raise ValidationError("No hay una compañía activa para este movimiento.")
            logger.warning(f"⚠️ [create_exit] No se pasó compañía, usando fallback: {company.code}")
        
        try:
            product = Product.objects.get(id=product_id)
            logger.info(f"   ✅ Producto encontrado: {product.code} - {product.name}")
        except Product.DoesNotExist as e:
            logger.error(f"❌ [create_exit] Producto no encontrado: {e}")
            raise
        
        try:
            location_from = Location.objects.get(id=location_from_id)
            logger.info(f"   ✅ Ubicación encontrada: {location_from.code} - {location_from.name}")
        except Location.DoesNotExist as e:
            logger.error(f"❌ [create_exit] Ubicación no encontrada: {e}")
            raise
        
        if quantity <= 0:
            logger.error(f"❌ [create_exit] Cantidad inválida: {quantity}")
            raise ValidationError("La cantidad debe ser mayor a cero")

        # ✅ Verificar stock ANTES de crear el movimiento
        stock_actual = InventoryService.get_stock_by_location(
            product.id, location_from.id, company
        )
        if stock_actual < quantity:
            logger.error(
                f"❌ Stock insuficiente: {stock_actual} < {quantity}"
            )
            raise ValidationError(
                f"Stock insuficiente para '{product.name}'. "
                f"Disponible: {stock_actual}, Solicitado: {quantity}"
            )
        
        logger.info("   📝 Creando movimiento...")
        movement = Movement.objects.create(
            product=product,
            type='EXIT',
            quantity=quantity,
            unit_price=unit_price,
            location_from=location_from,
            source_type=source_type,
            source_reference=source_reference,
            note=note,
            user=user,
            company=company,
        )
        
        logger.info(f"   ✅ Movimiento creado: ID {movement.id}")
        
        # ✅ ACTUALIZACIÓN DIRECTA DEL INVENTARIO
        logger.info("   🔄 Actualizando inventario directamente...")
        try:
            InventoryService.update_stock_from_movement(movement)
            logger.info("   ✅ Inventario actualizado correctamente")
        except Exception as e:
            logger.error(f"   ❌ ERROR actualizando inventario: {e}")
            import traceback
            logger.error(f"   Traceback: {traceback.format_exc()}")
            raise
        
        logger.info("🔴 [create_exit] FINALIZADO EXITOSAMENTE")
        logger.info("=" * 80)
        return movement
    
    @staticmethod
    @transaction.atomic
    def create_transfer(product_id, quantity, location_from_id, location_to_id, 
                        note='', user=None, unit_price=0, company=None):
        """Trasladar producto de una ubicación a otra"""
        
        if company is None:
            company = Company.get_active()
            if not company:
                raise ValidationError("No hay una compañía activa para este movimiento.")
            logger.warning(f"⚠️ No se pasó compañía a create_transfer, usando fallback: {company.code}")
        
        logger.info(f"🔴 CREANDO TRASLADO para compañía {company.code}")
        
        product = Product.objects.get(id=product_id)
        location_from = Location.objects.get(id=location_from_id)
        location_to = Location.objects.get(id=location_to_id)
        
        if quantity <= 0:
            raise ValidationError("La cantidad debe ser mayor a cero")
        
        if location_from == location_to:
            raise ValidationError("Origen y destino no pueden ser la misma ubicación")
        
        # ✅ Verificar stock en origen
        stock_actual = InventoryService.get_stock_by_location(
            product.id, location_from.id, company
        )
        if stock_actual < quantity:
            raise ValidationError(
                f"Stock insuficiente para '{product.name}' en '{location_from.code}'. "
                f"Disponible: {stock_actual}, Solicitado: {quantity}"
            )
        
        movement = Movement.objects.create(
            product=product,
            type='TRANSFER',
            quantity=quantity,
            unit_price=unit_price,
            location_from=location_from,
            location_to=location_to,
            note=note,
            user=user,
            company=company,
        )
        
        logger.info(f"   ✅ Movimiento creado: ID {movement.id}")
        
        # ✅ ACTUALIZACIÓN DIRECTA: restar de origen, sumar a destino
        logger.info("   🔄 Actualizando inventario (restar origen)...")
        exit_movement = Movement.objects.create(
            product=product,
            type='EXIT',
            quantity=quantity,
            unit_price=unit_price,
            location_from=location_from,
            source_type='MANUAL',
            source_reference=movement.source_reference or f"TRANSFER-{movement.id}",
            note=f"Traslado a {location_to.code}",
            user=user,
            company=company,
        )
        InventoryService.update_stock_from_movement(exit_movement)
        
        logger.info("   🔄 Actualizando inventario (sumar destino)...")
        entry_movement = Movement.objects.create(
            product=product,
            type='ENTRY',
            quantity=quantity,
            unit_price=unit_price,
            location_to=location_to,
            source_type='MANUAL',
            source_reference=movement.source_reference or f"TRANSFER-{movement.id}",
            note=f"Traslado desde {location_from.code}",
            user=user,
            company=company,
        )
        InventoryService.update_stock_from_movement(entry_movement)
        
        logger.info("   ✅ Inventario actualizado correctamente")
        return movement


# ============================================================
# SERVICIOS DE INVENTARIO CONTABLE
# ============================================================

class InventoryService:
    """Servicios de gestión contable de inventario"""
    
    @staticmethod
    def get_stock_by_location(product_id, location_id, company=None):
        """Obtener stock de un producto en una ubicación específica"""
        try:
            queryset = Inventory.objects.filter(product_id=product_id, location_id=location_id)
            if company:
                queryset = queryset.filter(company=company)
            
            inventory = queryset.first()
            
            if inventory:
                logger.info(f"🔴 Stock encontrado: {inventory.quantity} para producto {product_id} en ubicación {location_id}")
                return inventory.quantity
            else:
                logger.info(f"🔴 No hay stock para producto {product_id} en ubicación {location_id}")
                return 0
        except Exception as e:
            logger.error(f"❌ Error obteniendo stock: {e}")
            return 0


    @staticmethod
    def find_location_with_stock(product, company, required_quantity=0):
        """
        Encuentra la primera ubicación que tenga stock disponible del producto.
        
        Args:
            product: Instancia de Product
            company: Instancia de Company
            required_quantity: Cantidad mínima requerida (opcional)
        
        Returns:
            Instancia de Location o None
        """
        from .models import Inventory
        
        inventories = Inventory.objects.filter(
            product=product,
            company=company,
            quantity__gt=0
        ).order_by('-quantity')
        
        for inv in inventories:
            if inv.location and inv.quantity >= required_quantity:
                return inv.location
        
        # Si no hay ninguna con stock suficiente, devolver la que más tenga
        first = inventories.first()
        return first.location if first and first.location else None
    
    @staticmethod
    def get_total_stock(product_id, company=None):
        """Obtener stock total de un producto en todas las ubicaciones"""
        queryset = Inventory.objects.filter(product_id=product_id)
        if company:
            queryset = queryset.filter(company=company)
        return sum(inv.quantity for inv in queryset) if queryset else 0
    
    @staticmethod
    @transaction.atomic
    def update_stock_from_movement(movement):
        """
        Actualizar inventario desde un movimiento físico.

        ⚠️ Usa QuerySet.update() en lugar de instance.save() para evitar
        disparar señales post_save de Inventory (recursión infinita).

        ⚠️ Usa threading.local() para evitar re-entrada.
        """
        import threading
        
        # ✅ threading.local() correctamente implementado
        if not hasattr(threading.current_thread(), '_inventory_lock'):
            threading.current_thread()._inventory_lock = threading.local()
        
        lock = threading.current_thread()._inventory_lock
        
        if getattr(lock, 'updating', False):
            logger.warning("⚠️ Re-entrada detectada en update_stock_from_movement, abortando")
            return None
        
        lock.updating = True
        try:
            return InventoryService._do_update_stock_from_movement(movement)
        finally:
            lock.updating = False
    
    @staticmethod
    @transaction.atomic
    def _do_update_stock_from_movement(movement):
        """Lógica real de actualización (protegida contra recursión)"""
        logger.info("=" * 80)
        logger.info("🔴 [_do_update_stock_from_movement] INICIANDO")
        logger.info(f"   Movimiento ID: {movement.id}")
        logger.info(f"   Tipo: {movement.type}")
        logger.info(f"   Producto: {movement.product.name} (ID: {movement.product.id})")
        logger.info(f"   Cantidad: {movement.quantity}")
        logger.info(f"   Compañía: {movement.company.code}")

        location = movement.location_to or movement.location_from

        if not location:
            logger.warning(
                f"⚠️ Movimiento {movement.id} sin ubicación, no se actualiza inventario"
            )
            logger.info("=" * 80)
            return None

        logger.info(f"   Ubicación: {location.code} (ID: {location.id})")

        try:
            # ✅ get_or_create
            inventory, created = Inventory.objects.get_or_create(
                product=movement.product,
                location=location,
                company=movement.company,
                defaults={
                    'quantity': 0,
                    'total_value': Decimal('0.00'),
                }
            )

            logger.info(
                f"   {'✅ Creado' if created else '✅ Encontrado'} registro de inventario"
            )
            logger.info(f"   Cantidad actual: {inventory.quantity}")

            old_quantity = inventory.quantity or 0
            new_quantity = old_quantity
            new_total_value = Decimal(str(inventory.total_value or 0))

            if movement.type == 'ENTRY':
                logger.info("   📥 Procesando ENTRADA...")
                new_quantity = old_quantity + movement.quantity
                new_total_value = (
                    Decimal(str(inventory.total_value or 0))
                    + Decimal(str(movement.quantity))
                    * Decimal(str(movement.unit_price or 0))
                )
                logger.info(f"   Nueva cantidad: {new_quantity}")

            elif movement.type == 'EXIT':
                logger.info("   📤 Procesando SALIDA...")
                if old_quantity < movement.quantity:
                    logger.error(
                        f"   ❌ Stock insuficiente: {old_quantity} < {movement.quantity}"
                    )
                    raise ValidationError(
                        f"Stock insuficiente para {movement.product.name}. "
                        f"Disponible: {old_quantity}, Solicitado: {movement.quantity}"
                    )
                new_quantity = old_quantity - movement.quantity

                if new_quantity > 0 and old_quantity > 0:
                    avg_value = (
                        Decimal(str(inventory.total_value or 0))
                        / Decimal(str(old_quantity))
                    )
                    new_total_value = avg_value * Decimal(str(new_quantity))
                else:
                    new_total_value = Decimal('0.00')

                logger.info(f"   Nueva cantidad: {new_quantity}")

            elif movement.type == 'TRANSFER':
                logger.info("   🔄 TRASLADO detectado (no actualiza inventario directamente)")
                logger.info("=" * 80)
                return inventory

            elif movement.type == 'ADJUSTMENT':
                logger.info("   ⚙️ Procesando AJUSTE...")
                # ✅ El PhysicalCount maneja los ajustes directamente
                # Si llega aquí, tratamos como ENTRY o EXIT según location
                if movement.location_to and not movement.location_from:
                    # Es una entrada por ajuste
                    new_quantity = old_quantity + movement.quantity
                    logger.info(f"   Ajuste tipo ENTRADA → nueva cantidad: {new_quantity}")
                elif movement.location_from and not movement.location_to:
                    # Es una salida por ajuste
                    new_quantity = max(0, old_quantity - movement.quantity)
                    logger.info(f"   Ajuste tipo SALIDA → nueva cantidad: {new_quantity}")
                else:
                    logger.warning("   ⚠️ Movimiento ADJUSTMENT sin location_from ni location_to definidos")
                    logger.info("=" * 80)
                    return inventory
                
                new_total_value = Decimal(str(inventory.total_value or 0))
            
            else:
                logger.warning(f"   ⚠️ Tipo de movimiento no reconocido: {movement.type}")
                logger.info("=" * 80)
                return inventory

            # ✅ CLAVE: usar QuerySet.update() para evitar señales post_save
            updated_rows = Inventory.objects.filter(pk=inventory.pk).update(
                quantity=new_quantity,
                total_value=new_total_value,
                updated_at=timezone.now(),
            )
            logger.info(f"   ✅ {updated_rows} fila(s) actualizada(s) en BD")

            inventory.refresh_from_db()

            logger.info("   ✅ Inventario actualizado exitosamente")
            logger.info(f"   Cantidad final: {inventory.quantity}")
            logger.info(f"   Valor total final: {inventory.total_value}")
            logger.info("🔴 [_do_update_stock_from_movement] FINALIZADO")
            logger.info("=" * 80)

            return inventory

        except ValidationError:
            logger.info("=" * 80)
            raise
        except Exception as e:
            logger.error(f"❌ [_do_update_stock_from_movement] Error: {e}")
            import traceback
            logger.error(f"   Traceback: {traceback.format_exc()}")
            logger.info("=" * 80)
            raise

    @staticmethod
    @transaction.atomic
    def confirm_physical_count(count_id):
        """Confirmar un conteo físico y ajustar stock"""
        count = PhysicalCount.objects.get(id=count_id)
        
        if count.status != 'DRAFT':
            raise ValidationError("Solo se pueden confirmar conteos en borrador")
        
        inventory, created = Inventory.objects.get_or_create(
            product=count.product,
            location=count.location,
            company=count.company,
            defaults={
                'quantity': 0,
                'total_value': 0,
            }
        )
        inventory.quantity = count.counted_quantity
        inventory.total_value = inventory.quantity
        inventory.save()
        
        count.status = 'CONFIRMED'
        count.save()
        
        return count

    @staticmethod
    @transaction.atomic
    def confirm_delivery_note(note_id, user=None):
        """
        ✅ Confirmar una Nota de Entrega.
        - Crea movimientos de salida (resta stock)
        - Marca la nota como CONFIRMADA
        - Actualiza la orden de venta a DELIVERED
        - Genera la factura de venta
        """
        from .models import DeliveryNote, Movement
        from django_erp.sales.models import SaleOrder
        from django_erp.sales.services import SaleService
        
        logger.info("=" * 80)
        logger.info("🔴 [confirm_delivery_note] INICIANDO CONFIRMACIÓN")
        logger.info(f"   note_id: {note_id}")
        
        try:
            note = DeliveryNote.objects.get(id=note_id)
            logger.info(f"   ✅ Nota encontrada: {note.number}")
            logger.info(f"   Estado actual: {note.status}")
        except DeliveryNote.DoesNotExist as e:
            logger.error(f"❌ Nota no encontrada: {e}")
            raise
        
        if note.status != 'DRAFT':
            logger.warning(f"⚠️ Nota en estado '{note.get_status_display()}', no se puede confirmar")
            raise ValidationError(f"No se puede confirmar una nota en estado '{note.get_status_display()}'.")
        
        if not note.delivery_lines.exists():
            logger.warning("⚠️ Nota sin líneas")
            raise ValidationError("No se puede confirmar una nota sin líneas.")
        
        logger.info(f"   📊 Líneas a procesar: {note.delivery_lines.count()}")
        
        # ✅ Procesar cada línea y crear movimientos de salida
        for idx, line in enumerate(note.delivery_lines.all(), 1):
            logger.info(f"   📝 Procesando línea {idx}:")
            logger.info(f"      - Producto: {line.product.name}")
            logger.info(f"      - Cantidad: {line.quantity}")
            logger.info(f"      - Ubicación: {line.location.code}")
            
            # Verificar stock disponible
            stock = InventoryService.get_stock_by_location(line.product.id, line.location.id, line.company)
            logger.info(f"      - Stock disponible: {stock}")
            
            if stock < line.quantity:
                logger.error(f"      ❌ Stock insuficiente")
                raise ValidationError(
                    f"Stock insuficiente para '{line.product.name}' en la ubicación '{line.location.code}'. "
                    f"Disponible: {stock}, Requerido: {line.quantity}"
                )
            
            logger.info("      🚀 Creando movimiento de salida...")
            WarehouseService.create_exit(
                product_id=line.product.id,
                quantity=line.quantity,
                location_from_id=line.location.id,
                unit_price=line.product.sale_price,
                source_type='SALE',
                source_reference=note.number,
                note=f"Entrega {note.number} - {note.customer_name or note.customer.name if note.customer else 'Sin cliente'}",
                user=user or note.user,
                company=line.company
            )
            logger.info(f"      ✅ Línea {idx} procesada exitosamente")
        
        # ✅ Marcar nota como CONFIRMADA
        note.status = 'CONFIRMED'
        note.save()
        logger.info(f"   ✅ Nota {note.number} marcada como CONFIRMADA")
        
        # ✅ Buscar la orden de venta asociada y marcarla como DELIVERED
        # Buscar por número de nota en la referencia o por cliente
        sale_order = None
        
        # Intentar encontrar la orden por la referencia en las líneas
        if note.delivery_lines.exists():
            first_line = note.delivery_lines.first()
            # Buscar movimientos con source_reference = note.number
            from .models import Movement
            movement = Movement.objects.filter(
                source_reference=note.number,
                source_type='SALE'
            ).first()
            if movement:
                # Buscar la orden por el número de referencia
                sale_order = SaleOrder.objects.filter(
                    number=movement.source_reference,
                    company=note.company
                ).first()
        
        # Si no se encontró, buscar por cliente y fecha
        if not sale_order and note.customer:
            sale_order = SaleOrder.objects.filter(
                customer=note.customer,
                company=note.company,
                status='CONFIRMED'
            ).order_by('-date').first()
        
        if sale_order:
            logger.info(f"   🔗 Orden de venta encontrada: {sale_order.number}")
            try:
                # ✅ Marcar la orden como entregada (esto genera la factura)
                SaleService.deliver_order(sale_order, user)
                logger.info(f"   ✅ Orden {sale_order.number} marcada como DELIVERED")
            except Exception as e:
                logger.error(f"   ❌ Error al marcar la orden como entregada: {e}")
                # No bloqueamos la confirmación de la nota
        else:
            logger.warning("   ⚠️ No se encontró una orden de venta asociada a esta nota")
        
        logger.info("✅ [confirm_delivery_note] CONFIRMACIÓN COMPLETADA EXITOSAMENTE")
        logger.info("=" * 80)
        return note

    @staticmethod
    @transaction.atomic
    def cancel_delivery_note(note_id, user=None):
        """Cancelar una Nota de Entrega (no revierte movimientos por simplicidad)."""
        from .models import DeliveryNote
        
        note = DeliveryNote.objects.get(id=note_id)
        if note.status == 'CANCELLED':
            return note
        if note.status == 'CONFIRMED':
            raise ValidationError("No se puede cancelar una nota ya confirmada.")
        
        note.status = 'CANCELLED'
        note.save()
        return note

    @staticmethod
    @transaction.atomic
    def confirm_receipt_note(note_id, user=None):
        """
        ✅ Confirmar una Nota de Recibo y crear movimientos de entrada.
        
        FLUJO CENTRALIZADO:
        1. Verifica estado DRAFT
        2. Crea movimientos de entrada (ENTRY)
        3. Marca la nota como CONFIRMED
        4. Si hay orden de compra asociada, la marca como RECEIVED y genera factura
        """
        from .models import ReceiptNote, Movement
        
        logger.info("=" * 80)
        logger.info("🔴 [confirm_receipt_note] INICIANDO CONFIRMACIÓN")
        logger.info(f"   note_id: {note_id}")
        
        try:
            note = ReceiptNote.objects.get(id=note_id)
            logger.info(f"   ✅ Nota encontrada: {note.number}")
            logger.info(f"   Estado actual: {note.status}")
        except ReceiptNote.DoesNotExist as e:
            logger.error(f"❌ Nota no encontrada: {e}")
            raise
        
        # ✅ Idempotencia: si ya está confirmada, no hacer nada
        if note.status == 'CONFIRMED':
            logger.info(f"   ℹ️ Nota {note.number} ya estaba confirmada")
            return note
        
        if note.status != 'DRAFT':
            logger.warning(f"⚠️ Nota en estado '{note.get_status_display()}', no se puede confirmar")
            raise ValidationError(
                f"No se puede confirmar una nota en estado '{note.get_status_display()}'."
            )
        
        if not note.receipt_lines.exists():
            logger.warning("⚠️ Nota sin líneas")
            raise ValidationError("No se puede confirmar una nota sin líneas.")
        
        logger.info(f"   📊 Líneas a procesar: {note.receipt_lines.count()}")
        
        # ✅ PASO 1: Crear movimientos de entrada
        for idx, line in enumerate(note.receipt_lines.all(), 1):
            logger.info(f"   📝 Procesando línea {idx}:")
            logger.info(f"      - Producto: {line.product.name}")
            logger.info(f"      - Cantidad: {line.quantity}")
            logger.info(f"      - Ubicación: {line.location.code}")
            
            logger.info("      🚀 Creando movimiento de entrada...")
            WarehouseService.create_entry(
                product_id=line.product.id,
                quantity=line.quantity,
                location_to_id=line.location.id,
                unit_price=line.product.purchase_price or line.product.sale_price,
                source_type='PURCHASE',
                source_reference=note.number,
                note=f"Recibo {note.number} - {note.supplier_name or (note.supplier.name if note.supplier else 'Sin proveedor')}",
                user=user or note.user,
                company=line.company
            )
            logger.info(f"      ✅ Línea {idx} procesada exitosamente")
        
        # ✅ PASO 2: Marcar nota como CONFIRMED
        note.status = 'CONFIRMED'
        note.save()
        logger.info(f"   ✅ Nota {note.number} marcada como CONFIRMADA")

        # ✅ PASO 3: Si hay orden de compra, finalizarla (marca RECEIVED + genera factura)
        if note.purchase_order_id:
            logger.info(f"🔗 Nota {note.number} vinculada a orden {note.purchase_order.number}")
            logger.info("   🔄 Llamando a PurchaseService.finalize_receipt()...")
            
            try:
                from django_erp.purchasing.services import PurchaseService
                PurchaseService.finalize_receipt(note.purchase_order, user)
                logger.info(f"   ✅ PurchaseService.finalize_receipt() completado")
            except Exception as e:
                logger.error(f"   ❌ Error al finalizar la orden: {e}")
                import traceback
                logger.error(f"   Traceback: {traceback.format_exc()}")
                raise
        else:
            logger.info("ℹ️ Nota no vinculada a una orden de compra, saltando finalización")
        
        logger.info("✅ [confirm_receipt_note] CONFIRMACIÓN COMPLETADA")
        logger.info("=" * 80)
        return note

    @staticmethod
    @transaction.atomic
    def cancel_receipt_note(note_id, user=None):
        """Cancelar una Nota de Recibo (no revierte movimientos por simplicidad)."""
        from .models import ReceiptNote
        
        note = ReceiptNote.objects.get(id=note_id)
        if note.status == 'CANCELLED':
            return note
        if note.status == 'CONFIRMED':
            raise ValidationError("No se puede cancelar una nota ya confirmada.")
        
        note.status = 'CANCELLED'
        note.save()
        return note