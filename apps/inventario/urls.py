from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    InsumoViewSet, RecetaViewSet, RecetaPorPlatoListView,
    UnidadMedidaViewSet, MovimientoInventarioViewSet, OrdenCompraViewSet,
)

router = DefaultRouter()
router.register(r'unidades-medida', UnidadMedidaViewSet, basename='unidadmedida')
router.register(r'insumos', InsumoViewSet)
router.register(r'recetas', RecetaViewSet)
router.register(r'movimientos', MovimientoInventarioViewSet, basename='movimientos')
router.register(r'ordenes-compra', OrdenCompraViewSet, basename='ordencompra')

urlpatterns = [
    path('', include(router.urls)),
    path('recetas-por-plato/', RecetaPorPlatoListView.as_view(), name='recetas_por_plato'),
]
