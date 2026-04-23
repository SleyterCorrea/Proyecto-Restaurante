"""
API URLs para la app menu.
Prefijo: /api/menu/
"""
from django.urls import path
from . import views

urlpatterns = [
    # GET /api/menu/catalogo/ → catálogo completo con platos disponibles
    path('catalogo/', views.catalogo_api, name='api_menu_catalogo'),
]
