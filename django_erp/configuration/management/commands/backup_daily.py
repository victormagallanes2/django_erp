# django_erp/configuration/management/commands/backup_daily.py
"""
Comando para crear el respaldo diario automático.

Uso:
    python manage.py backup_daily           # Solo si no existe uno hoy
    python manage.py backup_daily --force   # Forzar (ignora verificación)
    python manage.py backup_daily --cleanup # Solo aplicar retención

Programar con Task Scheduler (Windows) o cron (Linux/Mac).
"""

from django.core.management.base import BaseCommand
from django_erp.configuration.services import BackupService


class Command(BaseCommand):
    help = 'Crea un respaldo diario de la BD si no existe uno hoy.'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Forzar el respaldo aunque ya exista uno hoy.',
        )
        parser.add_argument(
            '--cleanup',
            action='store_true',
            help='Solo ejecutar la limpieza de respaldos viejos.',
        )
    
    def handle(self, *args, **options):
        self.stdout.write('=' * 70)
        self.stdout.write('📦 RESPALDO DIARIO DEL ERP')
        self.stdout.write('=' * 70)
        
        # ============================================================
        # Solo limpieza
        # ============================================================
        if options['cleanup']:
            deleted = BackupService.cleanup_old_backups()
            self.stdout.write(self.style.SUCCESS(
                f'✅ Limpieza completada: {deleted} archivo(s) borrado(s) '
                f'(retención: {BackupService.RETENTION_DAYS} días)'
            ))
            return
        
        # ============================================================
        # Respaldo
        # ============================================================
        force = options['force']
        
        try:
            backup = BackupService.create_daily_backup_if_needed(force=force)
            
            if backup is None:
                self.stdout.write(self.style.WARNING(
                    'ℹ️ Ya existe un respaldo completado hoy. Saltando.'
                ))
                self.stdout.write(self.style.WARNING(
                    '   Usa --force para crear uno adicional.'
                ))
                return
            
            # ✅ Éxito
            self.stdout.write(self.style.SUCCESS(
                f'✅ Respaldo creado exitosamente:'
            ))
            self.stdout.write(f'   Nombre: {backup.name}')
            self.stdout.write(f'   Tamaño: {backup.file_size_display}')
            self.stdout.write(f'   Estado: {backup.get_status_display()}')
            self.stdout.write(f'   Archivo: {backup.file_path}')
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(
                f'❌ Error al crear respaldo: {e}'
            ))
            raise SystemExit(1)