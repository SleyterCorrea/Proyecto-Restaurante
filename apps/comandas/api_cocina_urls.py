from django.urls import path
from . import views

urlpatterns = [
    # GET /api/cocina/pendientes/ (legacy)
    path('pendientes/', views.api_cocina_pendientes, name='api_cocina_pendientes'),
    # GET /api/cocina/comandas-activas/ — KDS main feed
    path('comandas-activas/', views.api_cocina_activas, name='api_cocina_activas'),
    # PATCH /api/cocina/lineas/<id>/cambiar-estado/ — KDS state change
    path('lineas/<int:pk>/cambiar-estado/', views.api_cocina_cambiar_estado, name='api_cocina_cambiar_estado'),
    # GET /api/cocina/resumen/ — KDS summary stats
    path('resumen/', views.api_cocina_resumen, name='api_cocina_resumen'),
]
