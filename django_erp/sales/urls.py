# sales/urls.py
from django.urls import path
from .views import get_product_price

app_name = 'sales'

urlpatterns = [
    path('get-product-price/', get_product_price, name='get_product_price'),
]