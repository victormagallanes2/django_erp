# django_erp/purchasing/services.py
from django.db import transaction
from django.core.exceptions import ValidationError
from django.apps import apps
from .models import PurchaseOrder
from decimal import Decimal
import logging
import traceback

logger = logging.getLogger(__name__)


class PurchaseService:
    """Servicios de compras"""
    
    @staticmethod
    @transaction.atomic
    def confirm_order(order, user=None):
        """Confirmar una orden de compra"""
        logger.info(f"🔴 Confirmando orden {order.number}")
        logger.info(f"   Estado actual: {order.status}")
        
        if not order.lines.exists():
            logger.error("   ❌ La orden no tiene líneas")
            raise ValidationError("No se puede confirmar una orden sin líneas")
        
        if order.status == 'ORDERED':
            logger.info("   ℹ️ La orden ya está confirmada")
            return order
        
        if order.status != 'DRAFT':
            logger.error(f"   ❌ La orden no está en borrador. Estado: {order.status}")
            raise ValidationError(f"Solo se pueden confirmar órdenes en borrador. Estado actual: {order.get_status_display()}")
        
        logger.info("   ✅ Cambiando estado a ORDERED...")
        order.status = 'ORDERED'
        order.save()
        
        logger.info(f"   ✅ Orden {order.number} confirmada exitosamente")
        return order
    
    @staticmethod
    @transaction.atomic
    def receive_order(order, user=None):
        """Recibir una orden de compra - Crea movimientos de entrada en el almacén"""
        print("=" * 80)
        print(f"📦 RECIBIENDO ORDEN {order.number}")
        print(f"   ID de la orden: {order.id}")
        print(f"   Estado actual: {order.status}")
        print(f"   Usuario: {user}")
        print("=" * 80)
        
        # ✅ Verificar líneas
        lines_count = order.lines.count()
        print(f"   📊 Líneas en la orden: {lines_count}")
        
        if lines_count == 0:
            print("   ⚠️ LA ORDEN NO TIENE LÍNEAS")
            raise ValidationError("No se puede recibir una orden sin líneas")
        
        # ✅ Mostrar cada línea
        for idx, line in enumerate(order.lines.all(), 1):
            print(f"   --- LÍNEA {idx} ---")
            print(f"      Producto ID: {line.product_id}")
            print(f"      Producto nombre: {line.product_name}")
            print(f"      ¿Tiene producto? {line.product is not None}")
            if line.product:
                print(f"      ¿Es servicio? {line.product.is_service}")
                print(f"      Producto activo: {line.product.is_active}")
            print(f"      Cantidad: {line.quantity}")
            print(f"      Precio: {line.unit_price}")
            print(f"      Ubicación ID: {line.location_id}")
        
        # ✅ Verificar módulo Warehouse
        if not apps.is_installed('django_erp.warehouse'):
            print("   ❌ Módulo Warehouse NO está instalado")
            raise ValidationError("El módulo Warehouse no está instalado")
        else:
            print("   ✅ Módulo Warehouse está instalado")
        
        # ✅ IMPORTANTE: Permitir procesar incluso si ya está RECEIVED
        # Pero solo si no tiene movimientos asociados
        if order.status == 'RECEIVED':
            print("   ⚠️ La orden ya está en estado RECEIVED")
            print("   🔍 Verificando si ya tiene movimientos...")
            
            # ✅ Verificar si ya tiene movimientos
            from django_erp.warehouse.models import Movement
            existing_movements = Movement.objects.filter(
                source_reference=order.number,
                source_type='PURCHASE'
            )
            
            if existing_movements.exists():
                print(f"   ℹ️ Ya tiene {existing_movements.count()} movimientos asociados")
                print("   ✅ No es necesario procesar nuevamente")
                return order
            else:
                print("   ⚠️ La orden está en RECEIVED pero NO tiene movimientos")
                print("   🔄 Procesando creación de movimientos...")
                # ✅ Continuar con la creación de movimientos
        
        # ✅ Solo permitir recibir si está en ORDERED o RECEIVED (sin movimientos)
        if order.status not in ['ORDERED', 'RECEIVED']:
            print(f"   ❌ La orden no está en estado 'Ordenada' o 'Recibida'. Estado: {order.status}")
            raise ValidationError("Solo se pueden recibir órdenes en estado 'Ordenada' o 'Recibida' (sin movimientos)")
        
        # ✅ Importar servicios de warehouse
        try:
            from django_erp.warehouse.services import WarehouseService
            from django_erp.warehouse.models import Location, Movement
            print("   ✅ Servicios de Warehouse importados correctamente")
        except ImportError as e:
            print(f"   ❌ Error importando Warehouse: {e}")
            raise ValidationError(f"Error importando Warehouse: {e}")
        
        # ✅ Crear movimiento de entrada por cada línea
        movements_created = 0
        
        for idx, line in enumerate(order.lines.all(), 1):
            print(f"   --- PROCESANDO LÍNEA {idx} ---")
            
            # ✅ Solo procesar si tiene producto
            if not line.product:
                print(f"      ⚠️ Línea sin producto, saltando...")
                continue
            
            print(f"      ✅ Producto: {line.product.name}")
            print(f"      ID: {line.product.id}")
            print(f"      ¿Es servicio? {line.product.is_service}")
            
            if line.product.is_service:
                print(f"      ℹ️ Es un servicio, no se crea movimiento de inventario")
                continue
            
            print(f"      ✅ Es un producto físico, creando movimiento...")
            
            # ✅ Determinar ubicación
            location_id = line.location.id if line.location else None
            print(f"      Ubicación ID: {location_id}")
            
            if not location_id:
                print("      🔍 Buscando ubicación por defecto...")
                default_location = Location.objects.filter(is_active=True).first()
                if default_location:
                    location_id = default_location.id
                    print(f"      ✅ Ubicación por defecto: {default_location.name} (ID: {location_id})")
                else:
                    print("      ❌ No hay ubicaciones disponibles")
                    raise ValidationError(
                        f"No hay ubicación para el producto {line.product.name}. "
                        "Crea una ubicación en el módulo de Almacén."
                    )
            
            # ✅ Verificar si ya existe un movimiento para esta línea
            existing_movement = Movement.objects.filter(
                source_reference=order.number,
                source_type='PURCHASE',
                product_id=line.product.id
            ).first()
            
            if existing_movement:
                print(f"      ⚠️ Ya existe un movimiento para este producto: ID {existing_movement.id}")
                print(f"      ℹ️ Saltando para evitar duplicados")
                continue
            
            # ✅ Crear el movimiento de entrada
            try:
                print(f"      🔄 Creando movimiento de entrada...")
                print(f"         Producto ID: {line.product.id}")
                print(f"         Cantidad: {line.quantity}")
                print(f"         Ubicación destino: {location_id}")
                print(f"         Precio unitario: {line.unit_price}")
                print(f"         Source Type: PURCHASE")
                print(f"         Source Reference: {order.number}")
                
                movement = WarehouseService.create_entry(
                    product_id=line.product.id,
                    quantity=line.quantity,
                    location_to_id=location_id,
                    unit_price=Decimal(str(line.unit_price)),
                    source_type='PURCHASE',
                    source_reference=order.number,
                    note=f"Recepción de compra {order.number} - {order.supplier.name}",
                    user=user or order.user
                )
                
                movements_created += 1
                print(f"      ✅ MOVIMIENTO CREADO: ID {movement.id}")
                print(f"         Tipo: {movement.type}")
                print(f"         Producto: {movement.product.name}")
                print(f"         Cantidad: {movement.quantity}")
                
            except Exception as e:
                print(f"      ❌ Error al crear movimiento: {str(e)}")
                import traceback
                traceback.print_exc()
                raise ValidationError(f"Error al crear movimiento para {line.product.name}: {str(e)}")
        
        # ✅ Verificar que se crearon movimientos
        if movements_created == 0:
            print("   ⚠️ NO SE CREARON MOVIMIENTOS")
            print("   Esto puede ser normal si todos los productos son servicios")
        else:
            print(f"   ✅ MOVIMIENTOS CREADOS: {movements_created}")
        
        # ✅ Cambiar estado a RECEIVED (si no lo está ya)
        if order.status != 'RECEIVED':
            print("   🔄 Cambiando estado a RECEIVED...")
            order.status = 'RECEIVED'
            order.save()
        else:
            print("   ℹ️ La orden ya estaba en estado RECEIVED")
        
        print(f"   ✅ Orden {order.number} procesada exitosamente")
        print("=" * 80)
        return order
    
    @staticmethod
    @transaction.atomic
    def cancel_order(order, user=None):
        """Cancelar una orden de compra"""
        logger.info(f"❌ Cancelando orden {order.number}")
        logger.info(f"   Estado actual: {order.status}")
        
        if order.status == 'CANCELLED':
            logger.info("   ℹ️ La orden ya está cancelada")
            return order
        
        if order.status == 'RECEIVED':
            raise ValidationError("No se puede cancelar una orden ya recibida")
        
        order.status = 'CANCELLED'
        order.save()
        
        logger.info(f"✅ Orden {order.number} cancelada")
        return order