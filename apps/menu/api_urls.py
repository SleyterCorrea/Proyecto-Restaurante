"""
API URLs para la app menu.
Prefijo: /api/menu/
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'categorias', views.CategoriaViewSet, basename='categoria')
router.register(r'platos', views.PlatoViewSet, basename='plato')

urlpatterns = [
    # GET /api/menu/catalogo/ → catálogo completo con platos disponibles
    path('catalogo/', views.catalogo_api, name='api_menu_catalogo'),
    path('', include(router.urls)),
]
