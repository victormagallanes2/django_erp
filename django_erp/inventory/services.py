# inventory/services.py - VERSIÓN COMPLETA CON MEJORAS PARA NOTAS DE ENTREGA
from django.db import transaction
from django.core.exceptions import ValidationError
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
        logger.info("   ℹ️ La señal post_save actualizará el inventario automáticamente")
        
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
        logger.info("   ℹ️ La señal post_save actualizará el inventario automáticamente")
        
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
        logger.info("   ℹ️ La señal post_save actualizará el inventario automáticamente")
        
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
    def get_total_stock(product_id, company=None):
        """Obtener stock total de un producto en todas las ubicaciones"""
        queryset = Inventory.objects.filter(product_id=product_id)
        if company:
            queryset = queryset.filter(company=company)
        return sum(inv.quantity for inv in queryset) if queryset else 0
    
    @staticmethod
    @transaction.atomic
    def update_stock_from_movement(movement):
        """Actualizar inventario desde un movimiento físico"""
        logger.info("=" * 80)
        logger.info("🔴 [update_stock_from_movement] INICIANDO ACTUALIZACIÓN")
        logger.info(f"   Movimiento ID: {movement.id}")
        logger.info(f"   Tipo: {movement.type}")
        logger.info(f"   Producto: {movement.product.name} (ID: {movement.product.id})")
        logger.info(f"   Cantidad: {movement.quantity}")
        
        location = movement.location_to or movement.location_from
        
        if not location:
            logger.warning(f"⚠️ [update_stock_from_movement] Movimiento {movement.id} sin ubicación, no se actualiza inventario")
            logger.info("=" * 80)
            return None
        
        logger.info(f"   Ubicación: {location.code} (ID: {location.id})")
        
        try:
            inventory, created = Inventory.objects.get_or_create(
                product=movement.product,
                location=location,
                company=movement.company,
                defaults={
                    'quantity': 0,
                    'total_value': 0,
                }
            )
            
            logger.info(f"   {'✅ Creado' if created else '✅ Encontrado'} registro de inventario")
            logger.info(f"   Cantidad actual: {inventory.quantity}")
            
            if movement.type == 'ENTRY':
                logger.info("   📥 Procesando ENTRADA...")
                inventory.quantity += movement.quantity
                # ✅ Actualizar valor total con el precio del movimiento
                inventory.total_value = inventory.quantity * movement.unit_price
                logger.info(f"   Nueva cantidad: {inventory.quantity}")
                    
            elif movement.type == 'EXIT':
                logger.info("   📤 Procesando SALIDA...")
                if inventory.quantity < movement.quantity:
                    logger.error(f"   ❌ Stock insuficiente: {inventory.quantity} < {movement.quantity}")
                    raise ValidationError(f"Stock insuficiente para {movement.product.name}. "
                                         f"Disponible: {inventory.quantity}, Solicitado: {movement.quantity}")
                inventory.quantity -= movement.quantity
                # ✅ Recalcular valor total con el precio promedio ponderado
                if inventory.quantity > 0:
                    # Mantener el valor total proporcional a la cantidad restante
                    inventory.total_value = inventory.quantity * (inventory.total_value / (inventory.quantity + movement.quantity))
                else:
                    inventory.total_value = 0
                logger.info(f"   Nueva cantidad: {inventory.quantity}")
                
            elif movement.type == 'TRANSFER':
                logger.info("   🔄 Procesando TRASLADO...")
                # Los traslados se manejan en dos pasos
                # No modificar el inventario aquí, se maneja con dos movimientos separados
                pass
            
            inventory.save()
            
            logger.info(f"   ✅ Inventario guardado exitosamente")
            logger.info(f"   Cantidad final: {inventory.quantity}")
            logger.info(f"   Valor total final: {inventory.total_value}")
            logger.info("🔴 [update_stock_from_movement] FINALIZADO")
            logger.info("=" * 80)
            
            return inventory
            
        except Exception as e:
            logger.error(f"❌ [update_stock_from_movement] Error: {e}")
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
        
        if not note.lines.exists():
            logger.warning("⚠️ Nota sin líneas")
            raise ValidationError("No se puede confirmar una nota sin líneas.")
        
        logger.info(f"   📊 Líneas a procesar: {note.lines.count()}")
        
        # ✅ Procesar cada línea y crear movimientos de salida
        for idx, line in enumerate(note.lines.all(), 1):
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
        if note.lines.exists():
            first_line = note.lines.first()
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
        Confirmar una Nota de Recibo y crear movimientos de entrada.
        """
        from .models import ReceiptNote, Movement
        
        logger.info("=" * 80)
        logger.info("🔴 [confirm_receipt_note] INICIANDO CONFIRMACIÓN DE NOTA DE RECIBO")
        logger.info(f"   note_id: {note_id}")
        
        try:
            note = ReceiptNote.objects.get(id=note_id)
            logger.info(f"   ✅ Nota encontrada: {note.number}")
            logger.info(f"   Estado actual: {note.status}")
            logger.info(f"   Orden de compra asociada: {note.purchase_order.number if note.purchase_order else 'Ninguna'}")
        except ReceiptNote.DoesNotExist as e:
            logger.error(f"❌ Nota no encontrada: {e}")
            raise
        
        if note.status != 'DRAFT':
            logger.warning(f"⚠️ Nota en estado '{note.get_status_display()}', no se puede confirmar")
            raise ValidationError(f"No se puede confirmar una nota en estado '{note.get_status_display()}'.")
        
        if not note.lines.exists():
            logger.warning("⚠️ Nota sin líneas")
            raise ValidationError("No se puede confirmar una nota sin líneas.")
        
        logger.info(f"   📊 Líneas a procesar: {note.lines.count()}")
        
        for idx, line in enumerate(note.lines.all(), 1):
            logger.info(f"   📝 Procesando línea {idx}:")
            logger.info(f"      - Producto: {line.product.name}")
            logger.info(f"      - Cantidad: {line.quantity}")
            logger.info(f"      - Ubicación: {line.location.code}")
            
            logger.info("      🚀 Creando movimiento de entrada...")
            WarehouseService.create_entry(
                product_id=line.product.id,
                quantity=line.quantity,
                location_to_id=line.location.id,
                unit_price=line.product.sale_price,
                source_type='PURCHASE',
                source_reference=note.number,
                note=f"Recibo {note.number} - {note.supplier_name or note.supplier.name if note.supplier else 'Sin proveedor'}",
                user=user or note.user,
                company=line.company
            )
            logger.info(f"      ✅ Línea {idx} procesada exitosamente")
        
        note.status = 'CONFIRMED'
        note.save()
        logger.info(f"   ✅ Nota {note.number} marcada como CONFIRMADA")

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
        
        logger.info("✅ [confirm_receipt_note] CONFIRMACIÓN COMPLETADA EXITOSAMENTE")
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