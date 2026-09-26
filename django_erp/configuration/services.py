# configuration/services.py
import os
import shutil
from datetime import datetime
from django.conf import settings
from django.utils import timezone
from .models import Company, Backup, Currency


class CompanyService:
    @staticmethod
    def get_active_company():
        return Company.get_active()


class BackupService:
    @staticmethod
    def create_backup(user=None, note=''):
        """Crear un respaldo con pg_dump (PostgreSQL)."""
        backup_dir = os.path.join(settings.BASE_DIR, 'backups')
        os.makedirs(backup_dir, exist_ok=True)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'backup_{timestamp}.sql'
        file_path = os.path.join(backup_dir, filename)

        db_url = os.getenv('DATABASE_URL', '')
        parsed = urlparse(db_url)

        env = os.environ.copy()
        env['PGPASSWORD'] = parsed.password or ''

        cmd = [
            'pg_dump',
            '-h', parsed.hostname or 'localhost',
            '-p', str(parsed.port or 5432),
            '-U', parsed.username or 'postgres',
            '-d', (parsed.path or '/django_erp').lstrip('/'),
            '-F', 'c',              # formato custom (comprimido)
            '-f', file_path,
        ]

        try:
            subprocess.run(cmd, check=True, env=env, capture_output=True)

            backup = Backup.objects.create(
                name=f'Respaldo {timestamp}',
                file_path=file_path,
                file_size=os.path.getsize(file_path),
                database_type='postgresql',
                status='COMPLETED',
                completed_at=timezone.now(),
                user=user,
                note=note,
            )
            return backup

        except subprocess.CalledProcessError as e:
            Backup.objects.create(
                name=f'Respaldo fallido {timestamp}',
                file_path='',
                status='FAILED',
                user=user,
                note=f'Error: {e.stderr.decode() if e.stderr else str(e)}',
            )
            raise Exception(f'Error al crear respaldo: {e.stderr.decode() if e.stderr else str(e)}')
    
    @staticmethod
    def get_backups():
        """Obtener todos los respaldos"""
        return Backup.objects.all().order_by('-created_at')
