# configuration/urls.py
from django.urls import path
from . import views

app_name = 'configuration'

urlpatterns = [
    path('backup/', views.backup_list, name='backup_list'),
    path('backup/create/', views.backup_create, name='backup_create'),
    path('backup/<int:backup_id>/download/', views.backup_download, name='backup_download'),
    path('backup/<int:backup_id>/delete/', views.backup_delete, name='backup_delete'),
]