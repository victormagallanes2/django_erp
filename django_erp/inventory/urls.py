# invoicing/urls.py
from django.urls import path
from . import views

app_name = 'invoicing'

urlpatterns = [
    path('get-product-stock/', views.get_product_stock, name='get_product_stock'),
]