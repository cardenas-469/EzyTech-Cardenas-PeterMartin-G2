from django.urls import path
from . import views

urlpatterns = [
    path('', views.product_list, name='product_list'),
    path('add/', views.product_create, name='product_create'),
    path('checkout/<int:product_id>/', views.order_checkout, name='order_checkout'),
    path('orders/', views.order_history, name='order_history'),
]
