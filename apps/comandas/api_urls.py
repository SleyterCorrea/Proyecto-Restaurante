"""
API URLs para la app comandas.
Prefijo: /api/comandas/
"""
from django.urls import path
from . import views

urlpatterns = [
    # POST /api/comandas/crear/                  → Crear nueva comanda
    path('crear/',                    views.api_crear_comanda, name='api_crear_comanda'),
    # PATCH /api/comandas/linea/<id>/editar/     → Editar una línea específica
    path('linea/<int:linea_id>/editar/', views.api_editar_linea,   name='api_editar_linea'),
    # POST /api/comandas/mesa/<id>/liberar/      → Liberar una mesa y cerrar comanda
    path('mesa/<int:mesa_id>/liberar/', views.api_liberar_mesa,   name='api_liberar_mesa'),
]
