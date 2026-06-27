from rest_framework import viewsets, status, generics
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import PageNumberPagination
from decimal import Decimal
from django.utils import timezone
from .models import UnidadMedida, Insumo, RecetaInsumo, MovimientoInventario, OrdenCompra
from .serializers import (
    UnidadMedidaSerializer, InsumoSerializer, RecetaInsumoSerializer,
    MovimientoInventarioSerializer, AjusteStockSerializer, RecetaPorPlatoSerializer,
    MermaSerializer, ReponerSerializer, OrdenCompraSerializer,
)
from apps.usuarios.permissions import EsAdmin
from apps.menu.models import Plato
from .services import InventarioService, obtener_insumos_criticos, obtener_stock_bajo
from apps.core.exceptions import AppError


class StandardResultsSetPagination(PageNumberPagination):
    """Paginación estándar para listados."""
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 500

class UnidadMedidaViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = UnidadMedida.objects.filter(activo=True).order_by('nombre')
    serializer_class = UnidadMedidaSerializer
    permission_classes = [IsAuthenticated]

class InsumoViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gestión de Insumos.
    Endpoints:
    - GET / - Lista todos los insumos (paginado)
    - POST / - Crea nuevo insumo (Admin)
    - GET /{id}/ - Ver detalle de insumo
    - PUT/DELETE /{id}/ - Actualizar/Eliminar (Admin)
    - GET /disponibles/ - Listar insumos para recetas
    - GET /criticos/ - Insumos con stock crítico
    - GET /stock-bajo/ - Insumos con stock bajo
    - POST /{id}/reponer/ - Reponer stock
    - POST /{id}/ajuste/ - Ajuste manual de stock
    - POST /{id}/merma/ - Registrar merma
    - GET /{id}/historial/ - Ver movimientos del insumo
    """
    queryset = Insumo.objects.all().order_by('nombre')
    serializer_class = InsumoSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination
    filterset_fields = ['activo', 'unidad_medida', 'categoria']

    def get_permissions(self):
        if self.action in ['list', 'retrieve', 'disponibles', 'criticos', 'stock_bajo', 'historial']:
            return [IsAuthenticated()]
        return [EsAdmin()]


    @action(detail=False, methods=['get'], url_path='disponibles')
    def disponibles(self, request):
        """Lista todos los insumos activos con información completa para recetas."""
        insumos = Insumo.objects.para_recetas()
        resultado = []
        for insumo in insumos:
            resultado.append({
                'id': insumo.id,
                'nombre': insumo.nombre,
                'stock_real': float(insumo.stock_real),
                'stock_minimo': float(insumo.stock_minimo),
                'unidad_medida': {
                    'id': insumo.unidad_medida.id,
                    'nombre': insumo.unidad_medida.nombre,
                    'abreviatura': insumo.unidad_medida.abreviatura
                }
            })
        return Response(resultado)

    @action(detail=False, methods=['get'], url_path='criticos')
    def criticos(self, request):
        """Retorna insumos críticos (stock <= mínimo) con platos afectados."""
        datos = obtener_insumos_criticos()
        return Response(datos)

    @action(detail=False, methods=['get'], url_path='stock-bajo')
    def stock_bajo(self, request):
        """Retorna insumos con stock bajo (entre 0 y mínimo)."""
        datos = obtener_stock_bajo()
        return Response(datos)

    @action(detail=True, methods=['post'], url_path='reponer')
    def reponer(self, request, pk=None):
        """Registra entrada/reposición de inventario."""
        serializer = ReponerSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        cantidad = serializer.validated_data['cantidad']
        observacion = serializer.validated_data.get('observacion', '') or 'Reposición de inventario'

        try:
            insumo = InventarioService.reponer(pk, cantidad, request.user, observacion)
        except AppError as exc:
            return Response(exc.as_dict(), status=exc.status_code)
        return Response(self.get_serializer(insumo).data)

    @action(detail=True, methods=['get'], url_path='historial')
    def historial(self, request, pk=None):
        """Devuelve los últimos 50 movimientos de un insumo."""
        insumo = self.get_object()
        movimientos = insumo.movimientos.select_related('usuario').order_by('-created_at')[:50]
        data = [{
            'id': m.id,
            'fecha': m.created_at.strftime('%d/%m/%Y %H:%M'),
            'tipo': m.tipo_movimiento,
            'tipo_label': m.get_tipo_movimiento_display(),
            'cantidad': float(m.cantidad),
            'stock_anterior': float(m.stock_anterior),
            'stock_nuevo': float(m.stock_nuevo),
            'usuario': m.usuario.username if m.usuario else '—',
            'observacion': m.observacion or '',
        } for m in movimientos]
        return Response(data)

    @action(detail=True, methods=['post'], url_path='ajuste')
    def ajuste(self, request, pk=None):
        """Realiza un ajuste manual de stock con lock pesimista."""
        # Validar input antes de tomar el lock
        serializer = AjusteStockSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        cantidad = serializer.validated_data['cantidad']
        motivo = serializer.validated_data['motivo']
        tipo = serializer.validated_data['tipo']

        try:
            insumo = InventarioService.ajustar(pk, cantidad, tipo, motivo, request.user)
        except AppError as exc:
            return Response(exc.as_dict(), status=exc.status_code)
        return Response(self.get_serializer(insumo).data)

    def destroy(self, request, *args, **kwargs):
        """
        Soft-delete: marca el insumo como inactivo en vez de borrarlo,
        para preservar el historial de movimientos (FK PROTECT).
        """
        try:
            insumo = InventarioService.cambiar_activo(kwargs.get('pk'), False)
        except AppError as exc:
            return Response(exc.as_dict(), status=exc.status_code)
        return Response({'ok': True, 'message': f'Insumo "{insumo.nombre}" desactivado.'})

    @action(detail=True, methods=['post'], url_path='reactivar')
    def reactivar(self, request, pk=None):
        """Reactiva un insumo previamente desactivado."""
        try:
            insumo = InventarioService.cambiar_activo(pk, True)
        except AppError as exc:
            return Response(exc.as_dict(), status=exc.status_code)
        return Response({'ok': True, 'message': f'Insumo "{insumo.nombre}" reactivado.'})

    @action(detail=True, methods=['post'], url_path='merma')
    def merma(self, request, pk=None):
        """Registra una merma (pérdida) con causa documentada."""
        serializer = MermaSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        cantidad = serializer.validated_data['cantidad']
        causa = serializer.validated_data['causa']
        observacion = serializer.validated_data.get('observacion', '')

        try:
            insumo = InventarioService.registrar_merma(
                pk, cantidad, causa, request.user, observacion
            )
        except AppError as exc:
            return Response(exc.as_dict(), status=exc.status_code)
        return Response(self.get_serializer(insumo).data)

    @action(detail=False, methods=['get'], url_path='reporte-pdf')
    def reporte_pdf(self, request):
        """Genera un reporte PDF del inventario actual."""
        from .services import generar_reporte_pdf
        from django.http import HttpResponse
        buffer = generar_reporte_pdf(request.user)
        response = HttpResponse(buffer, content_type='application/pdf')
        nombre = f'reporte_inventario_{timezone.now().strftime("%Y%m%d_%H%M")}.pdf'
        response['Content-Disposition'] = f'attachment; filename="{nombre}"'
        return response

class RecetaViewSet(viewsets.ModelViewSet):
    queryset = RecetaInsumo.objects.all()
    serializer_class = RecetaInsumoSerializer
    permission_classes = [EsAdmin]

class RecetaPorPlatoListView(generics.ListAPIView):
    queryset = Plato.objects.all().prefetch_related('receta', 'receta__insumo')
    serializer_class = RecetaPorPlatoSerializer
    permission_classes = [EsAdmin]


class MovimientoInventarioViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet de solo lectura para movimientos de inventario.
    Endpoints:
    - GET / - Lista movimientos (paginado, con filtros)
    - GET /?insumo=1 - Filtrar por insumo
    - GET /?tipo=CONSUMO - Filtrar por tipo de movimiento
    - GET /?fecha_desde=2026-01-01&fecha_hasta=2026-01-31 - Filtrar por rango de fechas
    """
    queryset = MovimientoInventario.objects.select_related('insumo', 'usuario').order_by('-created_at')
    serializer_class = MovimientoInventarioSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination
    filterset_fields = ['tipo_movimiento']

    def get_queryset(self):
        qs = super().get_queryset()
        insumo_id = self.request.query_params.get('insumo')
        tipo = self.request.query_params.get('tipo')
        fechaDesde = self.request.query_params.get('fecha_desde')
        fechaHasta = self.request.query_params.get('fecha_hasta')

        if insumo_id:
            qs = qs.filter(insumo_id=insumo_id)
        if tipo:
            qs = qs.filter(tipo_movimiento=tipo)
        if fechaDesde:
            qs = qs.filter(created_at__date__gte=fechaDesde)
        if fechaHasta:
            qs = qs.filter(created_at__date__lte=fechaHasta)

        return qs  # La paginación maneja el límite


# ─── Órdenes de Compra ──────────────────────────────────────────────────────
class OrdenCompraViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gestión de Órdenes de Compra.
    Endpoints:
    - GET / - Lista todas las órdenes
    - POST / - Crear orden (Admin)
    - POST /generar-automatica/ - Genera OC para insumos bajos/agotados
    - POST /{id}/enviar/ - Enviar orden al proveedor
    - POST /{id}/recibir/ - Recepcionar orden y actualizar stock
    - POST /{id}/cancelar/ - Cancelar orden
    """
    queryset = OrdenCompra.objects.select_related('creado_por', 'recibido_por').prefetch_related('items__insumo__unidad_medida')
    serializer_class = OrdenCompraSerializer
    permission_classes = [EsAdmin]

    def create(self, request, *args, **kwargs):
        """
        Crea una orden de compra desde una lista de items:
        body: { proveedor, notas, items: [{ insumo, cantidad_solicitada, costo_unitario }] }
        """
        try:
            orden = InventarioService.crear_orden(request.data, request.user)
        except AppError as exc:
            return Response(exc.as_dict(), status=exc.status_code)
        return Response(self.get_serializer(orden).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['post'], url_path='generar-automatica')
    def generar_automatica(self, request):
        """Genera automáticamente una orden con los insumos bajos/agotados."""
        try:
            orden = InventarioService.generar_orden_automatica(
                request.user, request.data.get('proveedor', '')
            )
        except AppError as exc:
            return Response(exc.as_dict(), status=exc.status_code)
        return Response(self.get_serializer(orden).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='enviar')
    def enviar(self, request, pk=None):
        """Cambia BORRADOR → ENVIADA."""
        try:
            orden = InventarioService.cambiar_estado_orden(pk, OrdenCompra.Estado.ENVIADA)
        except AppError as exc:
            return Response(exc.as_dict(), status=exc.status_code)
        return Response(self.get_serializer(orden).data)

    @action(detail=True, methods=['post'], url_path='recibir')
    def recibir(self, request, pk=None):
        """
        Marca como RECIBIDA y SUMA cada item al stock automáticamente, generando un MovimientoInventario ENTRADA por cada uno.
        body opcional: { items: [{id, cantidad_recibida}] } — si se omite, recibe cantidad_solicitada completa.
        """
        try:
            recepciones = {
                int(item['id']): Decimal(str(item.get('cantidad_recibida', 0)))
                for item in request.data.get('items', [])
            }
            orden = InventarioService.cambiar_estado_orden(
                pk, OrdenCompra.Estado.RECIBIDA, request.user, recepciones
            )
        except (KeyError, ValueError):
            return Response({'error': 'Datos de recepcion invalidos.'}, status=400)
        except AppError as exc:
            return Response(exc.as_dict(), status=exc.status_code)
        return Response(self.get_serializer(orden).data)

    @action(detail=True, methods=['post'], url_path='cancelar')
    def cancelar(self, request, pk=None):
        """Cancela una orden en BORRADOR o ENVIADA."""
        try:
            orden = InventarioService.cambiar_estado_orden(pk, OrdenCompra.Estado.CANCELADA)
        except AppError as exc:
            return Response(exc.as_dict(), status=exc.status_code)
        return Response(self.get_serializer(orden).data)
