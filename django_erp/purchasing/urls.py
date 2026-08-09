# django_erp/purchasing/urls.py
from django.urls import path
from . import views

app_name = 'purchasing'

urlpatterns = [
    path('purchase-order/<int:order_id>/generate-invoice/', 
         views.generate_invoice_from_purchase_order, 
         name='generate_invoice_from_purchase_order'),
    path('get-product-price/', 
         views.get_product_price, 
         name='get_product_price'),
]