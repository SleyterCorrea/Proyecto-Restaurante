"""
API URLs para la app mesas.
Prefijo: /api/mesas/
"""
from django.urls import path
from . import views

urlpatterns = [
    # GET /api/mesas/libres/         → Mesas disponibles (Pantalla 1)
    path('libres/',        views.api_mesas_libres,  name='api_mesas_libres'),
    # GET /api/mesas/estado-actual/  → Polling (Pantalla 2)
    path('estado-actual/', views.api_estado_actual, name='api_estado_actual'),
]
