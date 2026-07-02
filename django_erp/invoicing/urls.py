# invoicing/urls.py
from django.urls import path
from .views import generate_invoice_from_order

app_name = 'invoicing'

urlpatterns = [
    path(
        'sale-order/<int:order_id>/generate-invoice/',
        generate_invoice_from_order,
        name='generate_invoice_from_order'
    ),
]