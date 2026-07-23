# django_erp/purchasing/urls.py
from django.urls import path
from . import views

app_name = 'purchasing'

urlpatterns = [
    # Agregar aquí las URLs específicas del módulo de compras
    # Por ejemplo, para obtener precios de productos (similar a ventas)
    path('get-product-price/', views.get_product_price, name='get_product_price'),
]