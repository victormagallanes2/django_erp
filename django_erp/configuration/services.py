# configuration/services.py
import os
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse
from django.conf import settings
from django.utils import timezone
from .models import Backup, Company


class CompanyService:
    @staticmethod
    def get_active_company():
        return Company.get_active()


def _get_documents_folder():
    """
    Devuelve la ruta a la carpeta Documentos del usuario en Windows.
    Maneja OneDrive y el caso estándar.
    """
    home = Path.home()
    
    # OneDrive español
    onedrive_es = home / 'OneDrive' / 'Documentos'
    if onedrive_es.exists():
        return onedrive_es
    
    # OneDrive inglés
    onedrive_en = home / 'OneDrive' / 'Documents'
    if onedrive_en.exists():
        return onedrive_en
    
    # Documentos estándar (inglés)
    docs_en = home / 'Documents'
    if docs_en.exists():
        return docs_en
    
    # Documentos estándar (español)
    docs_es = home / 'Documentos'
    if docs_es.exists():
        return docs_es
    
    # Fallback
    return home


class CompanyService:
    @staticmethod
    def get_active_company():
        return Company.get_active()


class BackupService:
    """
    Servicio para gestionar respaldos de la base de datos.
    
    Proporciona:
    - create_backup(): respaldo manual (usado desde el admin)
    - create_daily_backup_if_needed(): respaldo automático diario (cron)
    - cleanup_old_backups(): borra respaldos antiguos según retención
    - get_latest_backup(): último respaldo completado
    """
    
    # ✅ Configuración
    RETENTION_DAYS = 30
    BACKUPS_SUBFOLDER = 'ERP_Respaldos'
    
    # ============================================================
    # RESPALDO MANUAL (desde el admin)
    # ============================================================
    
    @staticmethod
    def create_backup(user=None, note=''):
        """
        Crear un respaldo con pg_dump y guardarlo en Documentos.
        Este método se llama desde el admin (botón "+") y desde el cron.
        
        Returns:
            Backup: instancia del respaldo creado.
        """
        # ✅ Carpeta de respaldos en Documentos
        base_folder = _get_documents_folder()
        backup_dir = base_folder / BackupService.BACKUPS_SUBFOLDER
        backup_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'backup_{timestamp}.sql'
        file_path = str(backup_dir / filename)
        
        # ✅ Datos de conexión
        db_url = os.getenv('DATABASE_URL', '')
        parsed = urlparse(db_url)
        
        env = os.environ.copy()
        env['PGPASSWORD'] = parsed.password or ''
        
        # ✅ Comando pg_dump
        cmd = [
            'pg_dump',
            '-h', parsed.hostname or 'localhost',
            '-p', str(parsed.port or 5432),
            '-U', parsed.username or 'postgres',
            '-d', (parsed.path or '/django_erp').lstrip('/'),
            '-F', 'p',                  # formato plano SQL
            '--no-owner',
            '--no-privileges',
            '-f', file_path,
        ]
        
        # ✅ Compañía activa para el registro
        company = None
        if user:
            company = getattr(user, 'preferred_company', None)
        if not company:
            company = Company.get_active()
        if not company:
            company = Company.objects.filter(is_active=True).first()
        
        # ✅ Crear el registro en estado PROCESSING
        backup = Backup.objects.create(
            name=f'Respaldo {timestamp}',
            file_path=file_path,
            file_size=0,
            database_type='postgresql',
            status='PROCESSING',
            user=user,
            note=note,
            company=company,
        )
        
        try:
            # ✅ Ejecutar pg_dump
            subprocess.run(
                cmd,
                check=True,
                env=env,
                capture_output=True,
                text=True,
            )
            
            # ✅ Actualizar registro
            backup.file_size = os.path.getsize(file_path)
            backup.status = 'COMPLETED'
            backup.completed_at = timezone.now()
            backup.save(update_fields=['file_size', 'status', 'completed_at'])
            
            return backup
        
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr or str(e)
            backup.status = 'FAILED'
            backup.completed_at = timezone.now()
            backup.note = f'Error: {error_msg}'
            backup.save(update_fields=['status', 'completed_at', 'note'])
            raise Exception(f'Error al crear respaldo: {error_msg}')
        
        except Exception as e:
            backup.status = 'FAILED'
            backup.completed_at = timezone.now()
            backup.note = f'Error: {str(e)}'
            backup.save(update_fields=['status', 'completed_at', 'note'])
            raise
    
    # ============================================================
    # RESPALDO AUTOMÁTICO DIARIO
    # ============================================================
    
    @staticmethod
    def create_daily_backup_if_needed(user=None, force=False):
        """
        Crea un respaldo SOLO si no existe uno completado HOY.
        Diseñado para ser ejecutado por un cron/Task Scheduler diariamente.
        
        Args:
            user: usuario asociado (opcional, para auditoría).
            force: si True, ignora la verificación y crea el respaldo.
        
        Returns:
            Backup o None (si ya existía uno hoy y no se fuerza).
        """
        if not force:
            hoy = timezone.localtime(timezone.now()).date()
            
            # ✅ Verificar si ya hay un respaldo exitoso hoy
            existe = Backup.objects.filter(
                created_at__date=hoy,
                status='COMPLETED',
            ).exists()
            
            if existe:
                return None
        
        # ✅ Crear el respaldo
        note = 'Respaldo automático diario' if not force else 'Respaldo forzado'
        backup = BackupService.create_backup(user=user, note=note)
        
        # ✅ Retención: borrar archivos de respaldos viejos
        BackupService.cleanup_old_backups()
        
        return backup
    
    # ============================================================
    # RETENCIÓN
    # ============================================================
    
    @staticmethod
    def cleanup_old_backups():
        """
        Borra archivos locales de respaldos mayores a RETENTION_DAYS.
        Mantiene los registros en la BD por auditoría.
        
        Returns:
            int: cantidad de archivos borrados.
        """
        cutoff = timezone.now() - timedelta(days=BackupService.RETENTION_DAYS)
        
        old_backups = Backup.objects.filter(
            created_at__lt=cutoff,
            status='COMPLETED',
        )
        
        deleted = 0
        for backup in old_backups:
            if backup.file_path and os.path.exists(backup.file_path):
                try:
                    os.remove(backup.file_path)
                    deleted += 1
                except Exception as e:
                    print(f"⚠️ No se pudo borrar {backup.file_path}: {e}")
        
        return deleted
    
    # ============================================================
    # CONSULTAS
    # ============================================================
    
    @staticmethod
    def get_latest_backup():
        """Devuelve el último respaldo completado."""
        return Backup.objects.filter(
            status='COMPLETED',
        ).order_by('-created_at').first()
    
    @staticmethod
    def get_last_backup_date():
        """Fecha del último respaldo completado."""
        last = BackupService.get_latest_backup()
        if last:
            return timezone.localtime(last.created_at).date()
        return None
    
    @staticmethod
    def get_backups():
        """Todos los respaldos ordenados por fecha."""
        return Backup.objects.all().order_by('-created_at')