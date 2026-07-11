# configuration/services.py
import os
import shutil
from datetime import datetime
from django.conf import settings
from django.utils import timezone
from .models import Company, Backup


class CompanyService:
    @staticmethod
    def get_active_company():
        return Company.get_active()


class BackupService:
    """Servicio para gestionar respaldos de la base de datos"""
    
    @staticmethod
    def create_backup(user=None, note=''):
        """Crear un respaldo de la base de datos"""
        
        backup_dir = os.path.join(settings.BASE_DIR, 'backups')
        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'backup_{timestamp}.sqlite3'
        file_path = os.path.join(backup_dir, filename)
        
        try:
            db_path = str(settings.DATABASES['default']['NAME'])
            
            if db_path.endswith('.sqlite3'):
                shutil.copy2(db_path, file_path)
            
            backup = Backup.objects.create(
                name=f'Respaldo {timestamp}',
                file_path=file_path,
                file_size=os.path.getsize(file_path),
                database_type='sqlite',
                status='COMPLETED',
                completed_at=timezone.now(),
                user=user,
                note=note
            )
            
            return backup
            
        except Exception as e:
            Backup.objects.create(
                name=f'Respaldo fallido {timestamp}',
                file_path='',
                status='FAILED',
                user=user,
                note=f'Error: {str(e)}'
            )
            raise Exception(f'Error al crear respaldo: {str(e)}')
    
    @staticmethod
    def get_backups():
        """Obtener todos los respaldos"""
        return Backup.objects.all().order_by('-created_at')