"""
URLs para las vistas HTML del módulo mesas.
Prefijo: /mesero/
"""
from django.urls import path
from . import views

urlpatterns = [
    path('mesas/',          views.plano_mesas_view,  name='plano_mesas'),
    path('nueva-comanda/',  views.toma_pedidos_view, name='toma_pedidos'),
]
