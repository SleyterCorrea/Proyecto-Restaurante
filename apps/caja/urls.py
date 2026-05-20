from django.urls import path
from . import views

urlpatterns = [
    # Vistas HTML
    path('apertura/', views.apertura_caja_view, name='caja_apertura'),
    path('cobrar/', views.cobrar_view, name='caja_cobrar'),
    path('cierre/', views.cierre_caja_view, name='caja_cierre'),

    # API Endpoints
    path('api/apertura/', views.api_abrir_turno, name='api_caja_apertura'),
    path('api/cierre/', views.api_cerrar_turno, name='api_caja_cierre'),
    path('api/turno-activo/', views.api_turno_activo, name='api_caja_turno_activo'),
    path('api/historial/', views.api_historial_pagos, name='api_caja_historial'),

    # Cobro — acepta multi-pago (pagos: [...])
    path('api/comandas/<int:pk>/pagar/', views.api_pagar_comanda, name='api_comanda_pagar'),
    # Alias con ruta más simple para compatibilidad con cobrar.html CAJA
    path('api/pagar/<int:pk>/', views.api_pagar_comanda, name='api_caja_pagar'),

    # Pérdida (cliente no pagó)
    path('api/registrar-perdida/<int:pk>/', views.api_registrar_perdida, name='api_caja_perdida'),

    # PDF Boleta
    path('boleta/<int:pago_id>/', views.descargar_boleta_view, name='descargar_boleta'),
]

