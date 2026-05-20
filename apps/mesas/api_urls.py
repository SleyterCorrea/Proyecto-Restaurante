"""
API URLs para la app mesas.
Prefijo: /api/mesas/
"""
from django.urls import path
from . import views

urlpatterns = [
    # GET /api/mesas/libres/         → Mesas disponibles (Pantalla 1 - incluye grupos)
    path('libres/',        views.api_mesas_libres,  name='api_mesas_libres'),
    # GET /api/mesas/estado-actual/  → Polling (Pantalla 2 - incluye uniones)
    path('estado-actual/', views.api_estado_actual, name='api_estado_actual'),
    # GET /api/mesas/lista/           → Lista para filtros (Reportes)
    path('lista/',          views.api_mesas_list,    name='api_mesas_lista'),

    # ── Gestión de Mesas (Solo Admin) ────────────────────────────────────────
    path('crear/',              views.api_mesa_crear,    name='api_mesa_crear'),
    path('eliminar/<int:pk>/',  views.api_mesa_eliminar, name='api_mesa_eliminar'),

    # ── Uniones de Mesas ──────────────────────────────────────────────────────
    path('uniones/',                    views.api_uniones_list,   name='api_uniones_list'),
    path('union/crear/',                views.api_union_crear,    name='api_union_crear'),
    path('union/<int:pk>/disolver/',    views.api_union_disolver, name='api_union_disolver'),

    # ── Estados Específicos ───────────────────────────────────────────────────
    path('<int:pk>/limpiada/',          views.api_mesa_limpiada,  name='api_mesa_limpiada'),
]
