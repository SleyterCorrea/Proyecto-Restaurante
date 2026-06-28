"""
API endpoint: GET /api/menu/catalogo/
Devuelve el catálogo completo de platos agrupados por categoría.
Solo incluye platos con disponible=True.
"""
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.exceptions import ValidationError

from apps.usuarios.permissions import EsAdmin
from apps.inventario.services import obtener_insumos_criticos
from apps.core.exceptions import AppError
from .models import Categoria, Plato
from .serializers import CategoriaSerializer, PlatoSerializer
from .services import MenuService


def _receta_data(request):
    if 'receta' not in request.data:
        return None
    if hasattr(request.data, 'getlist'):
        return request.data.getlist('receta')
    return request.data.get('receta') or []


def _receta_snapshot(plato):
    return sorted(
        (
            receta.insumo_id,
            receta.cantidad_por_porcion,
            receta.merma_porcentaje,
            receta.activo,
        )
        for receta in plato.receta.filter(activo=True)
    )


def _receta_propuesta_snapshot(receta_data):
    return sorted(
        item
        for item in MenuService._normalizar_receta(receta_data)
        if item[3]
    )

class CategoriaViewSet(viewsets.ModelViewSet):
    queryset = Categoria.objects.all().order_by('orden', 'nombre')
    serializer_class = CategoriaSerializer
    permission_classes = [IsAuthenticated, EsAdmin]

    def perform_create(self, serializer):
        MenuService.guardar_categoria(serializer)

    def perform_update(self, serializer):
        MenuService.guardar_categoria(serializer)

    def perform_destroy(self, instance):
        try:
            MenuService.desactivar_categoria(instance)
        except AppError as exc:
            raise ValidationError({'detail': str(exc)})

class PlatoViewSet(viewsets.ModelViewSet):
    queryset = Plato.objects.prefetch_related('receta__insumo__unidad_medida').order_by('categoria__orden', 'nombre')
    serializer_class = PlatoSerializer
    permission_classes = [IsAuthenticated, EsAdmin]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def perform_create(self, serializer):
        try:
            instance = MenuService.guardar_plato(serializer, _receta_data(self.request))
        except AppError as exc:
            raise ValidationError({'detail': str(exc)})

    def perform_update(self, serializer):
        receta_data = _receta_data(self.request)
        try:
            motivo = str(self.request.data.get('motivo', '')).strip()
            MenuService.guardar_plato(
                serializer,
                receta_data,
                usuario=self.request.user,
                motivo=motivo,
                request=self.request,
            )
        except AppError as exc:
            raise ValidationError({'detail': str(exc)})

    def perform_destroy(self, instance):
        motivo = str(self.request.data.get('motivo', '')).strip()
        if not motivo:
            raise ValidationError({
                'motivo': 'El motivo es obligatorio para desactivar un plato.'
            })
        MenuService.desactivar_plato(
            instance,
            usuario=self.request.user,
            motivo=motivo,
            request=self.request,
        )

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated, EsAdmin])
    def insumos_criticos(self, request):
        """
        Retorna lista de insumos críticos (con stock bajo o negativo)
        y sus platos afectados.
        """
        criticos = obtener_insumos_criticos()
        return Response({
            'total': len(criticos),
            'insumos': criticos
        })

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, EsAdmin])
    def agregar_insumo(self, request, pk=None):
        """
        Agrega un insumo a la receta del plato.
        POST /api/menu/platos/{id}/agregar_insumo/
        Body: {
            "insumo_id": 1,
            "cantidad_por_porcion": 100,
            "merma_porcentaje": 5
        }
        """
        try:
            receta = MenuService.agregar_insumo(
                self.get_object(),
                request.data,
                usuario=request.user,
                motivo=request.data.get('motivo'),
                request=request,
            )
            return Response({
                'id': receta.id,
                'mensaje': 'Insumo agregado/actualizado en la receta'
            })
        except AppError as exc:
            return Response(exc.as_dict(), status=exc.status_code)

    @action(detail=True, methods=['delete'], permission_classes=[IsAuthenticated, EsAdmin])
    def eliminar_insumo(self, request, pk=None):
        """
        Elimina un insumo de la receta del plato.
        DELETE /api/menu/platos/{id}/eliminar_insumo/?insumo_id={insumo_id}
        """
        insumo_id = request.query_params.get('insumo_id')
        if not insumo_id:
            return Response(
                {'error': 'Se requiere insumo_id'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            MenuService.eliminar_insumo(
                self.get_object(),
                insumo_id,
                usuario=request.user,
                motivo=(
                    request.data.get('motivo')
                    or request.query_params.get('motivo')
                ),
                request=request,
            )
            return Response({'mensaje': 'Insumo eliminado de la receta'})
        except AppError as exc:
            return Response(exc.as_dict(), status=exc.status_code)


@require_GET
def catalogo_api(request):
    """
    Responde con la lista de categorías y sus platos disponibles.
    Formato:
    {
      "categorias": [
        { "id": 1, "nombre": "Entradas", "icono": "bi-egg-fried",
          "platos": [{ "id": 1, "nombre": "...", "precio": "12.50", "imagen": "..." }] }
      ]
    }
    """
    categorias = []
    for cat in Categoria.objects.prefetch_related('platos').all():
        platos_disponibles = cat.platos.filter(disponible=True)
        if platos_disponibles.exists():
            categorias.append({
                'id':     cat.pk,
                'nombre': cat.nombre,
                'icono':  cat.icono,
                'platos': [
                    {
                        'id':          p.pk,
                        'nombre':      p.nombre,
                        'descripcion': p.descripcion,
                        'precio':      str(p.precio),
                        'imagen':      p.imagen_url(),
                        'tiempo_prep': p.tiempo_prep,
                    }
                    for p in platos_disponibles
                ],
            })

    return JsonResponse({'categorias': categorias})
