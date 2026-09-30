@echo off
cd /d C:\Users\victor\django_erp
call C:\Users\victor\venv\Scripts\activate.bat
python manage.py backup_daily
exit /b %ERRORLEVEL%