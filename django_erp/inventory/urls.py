# invoicing/urls.py
from django.urls import path
from . import views

app_name = 'invoicing'

urlpatterns = [
    path('get-available-quantity/', views.get_available_quantity, name='get_available_quantity'),
]