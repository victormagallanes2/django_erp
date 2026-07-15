# invoicing/urls.py
from django.urls import path
from . import views

app_name = 'invoicing'

urlpatterns = [
    path('get-product-price/', views.get_product_price, name='get_product_price'),
]