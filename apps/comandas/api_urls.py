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
    path('linea/<int:pk>/editar/', views.api_linea_detail,   name='api_editar_linea'),
    # POST /api/comandas/mesa/<id>/liberar/      → Liberar una mesa y cerrar comanda
    path('mesa/<int:mesa_id>/liberar/', views.api_liberar_mesa,   name='api_liberar_mesa'),
    # POST /api/comandas/<id>/platos/             → Agregar plato a comanda
    path('<int:pk>/platos/', views.api_agregar_plato_comanda, name='api_agregar_plato_comanda'),
    # POST /api/comandas/<id>/entregar/           → Marcar ítems LISTO como ENTREGADO
    path('<int:pk>/entregar/', views.api_marcar_pedido_entregado, name='api_marcar_pedido_entregado'),
]
