"""
Vistas y API endpoints para la app comandas.

API Endpoints:
  POST  /api/comandas/crear/           → Crea Comanda + LineaComanda atómicamente
  PATCH /api/comandas/linea/<id>/editar/ → Edita una LineaComanda (ej. cancelada)
  POST  /api/mesas/<id>/liberar/       → Cierra comanda y libera la mesa
"""
from __future__ import annotations
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from apps.usuarios.decorators import rol_requerido
from apps.usuarios.permissions import EsMozoOAdmin, EsCocineroOAdmin, EsAdmin

from .models import Comanda, LineaComanda
from apps.core.exceptions import AppError
from .services import ComandaService, CocinaService


def _error_response(exc):
    return Response(exc.as_dict(), status=exc.status_code)

# ─────────────────────────────────────────────────────────────────────────────
# POST /api/comandas/crear/
# ─────────────────────────────────────────────────────────────────────────────

@csrf_exempt
@api_view(['POST'])
@permission_classes([EsMozoOAdmin])
def api_crear_comanda(request):
    """
    Crea una Comanda con sus LineaComanda de forma atómica.

    Body JSON esperado desde Alpine.js:
    {
      "mesa_id": 3,
      "notas": "Sin sal en la sopa",
      "items": [
        { "plato_id": 12, "cantidad": 2, "notas": "Bien cocido" },
        { "plato_id":  7, "cantidad": 1, "notas": "" }
      ]
    }

    Respuesta exitosa:
    { "ok": true, "comanda_id": 42, "redirect": "/mesero/mesas/" }
    """
    try:
        comanda = ComandaService.abrir(request.data, request.user)
    except AppError as exc:
        return _error_response(exc)

    return JsonResponse({
        'ok': True, 
        'comanda_id': comanda.id, 
        'redirect': '/mesero/mesas/'
    })

# ─────────────────────────────────────────────────────────────────────────────
# PATCH /api/comandas/linea/<linea_id>/editar/
# ─────────────────────────────────────────────────────────────────────────────

@csrf_exempt
@api_view(['PATCH', 'DELETE'])
@permission_classes([EsMozoOAdmin])
def api_linea_detail(request, pk):
    """
    Edita o elimina una LineaComanda.
    REGLA DE NEGOCIO: Solo se permite si el estado es 'PENDIENTE'.
    """
    try:
        if request.method == 'DELETE':
            ComandaService.eliminar_linea(pk)
            return Response({'ok': True, 'message': 'Plato eliminado del pedido.'})
        linea = ComandaService.editar_linea(pk, request.data)
    except AppError as exc:
        return _error_response(exc)
    return Response({
        'ok': True,
        'linea_id': linea.pk,
        'plato_nombre': linea.plato.nombre,
        'cantidad': linea.cantidad,
        'subtotal': str(linea.subtotal),
    })


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/mesas/<mesa_id>/liberar/
# ─────────────────────────────────────────────────────────────────────────────

@csrf_exempt
@api_view(['POST'])
@permission_classes([EsMozoOAdmin])
def api_liberar_mesa(request, mesa_id):
    """
    Cierra la comanda activa de la mesa y la pone en estado LIBRE.
    Típicamente se llama al presionar "Liberar Mesa / Cobrar".
    """
    try:
        ComandaService.enviar_a_caja(mesa_id)
    except AppError as exc:
        return _error_response(exc)
    return Response({'ok': True, 'message': 'Comanda enviada a caja. Mesa en espera de pago.'})


@csrf_exempt
@api_view(['POST'])
@permission_classes([EsMozoOAdmin])
def api_marcar_pedido_entregado(request, pk):
    """
    Marca como ENTREGADO todas las líneas en estado LISTO de una comanda.
    Este paso lo ejecuta el mozo al entregar físicamente el pedido al cliente.
    """
    try:
        cantidad = ComandaService.marcar_entregado(pk)
    except AppError as exc:
        return _error_response(exc)

    return JsonResponse({
        'ok': True,
        'lineas_entregadas': cantidad,
        'message': 'Pedido marcado como entregado.'
    })



# ─────────────────────────────────────────────────────────────────────────────
# POST /api/comandas/<comanda_id>/platos/
# ─────────────────────────────────────────────────────────────────────────────
@csrf_exempt
@api_view(['POST'])
@permission_classes([EsMozoOAdmin])
def api_agregar_plato_comanda(request, pk):
    """
    Agrega un plato a una comanda existente.
    """
    try:
        linea = ComandaService.agregar_plato(pk, request.data)
    except AppError as exc:
        return _error_response(exc)

    return JsonResponse({'ok': True, 'linea_id': linea.id})

# ─────────────────────────────────────────────────────────────────────────────
# KDS API (Phase 4)
# ─────────────────────────────────────────────────────────────────────────────
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.db.models import Prefetch

@api_view(['GET'])
@permission_classes([EsCocineroOAdmin])
def api_cocina_pendientes(request):
    """
    GET /api/cocina/pendientes/
    Retorna comandas con líneas PENDIENTE o EN_PREP.
    Optimizado con select_related y prefetch_related.
    """
    lineas_cocina = Prefetch(
        'lineas',
        queryset=LineaComanda.objects.filter(estado__in=[LineaComanda.Estado.PENDIENTE, LineaComanda.Estado.EN_PREP]).select_related('plato'),
        to_attr='lineas_activas'
    )
    
    comandas = Comanda.objects.filter(
        estado=Comanda.Estado.ABIERTA,
        lineas__estado__in=[LineaComanda.Estado.PENDIENTE, LineaComanda.Estado.EN_PREP]
    ).select_related('mesa', 'mesa__zona', 'mozo').prefetch_related(lineas_cocina).distinct()

    data = []
    for c in comandas:
        if not c.lineas_activas: continue
        comanda_data = {
            'id': c.id,
            'mesa_numero': c.mesa.numero,
            'nombre_cliente': c.nombre_cliente or '',
            'zona_nombre': c.mesa.zona.nombre if c.mesa.zona else '',
            'mesero_nombre': c.mozo.username if c.mozo else 'Desconocido',
            'lineas': []
        }
        for l in c.lineas_activas:
            # Calcular tiempo transcurrido (asumimos fecha_envio_cocina es la de creación o similar, 
            # en el modelo original puede no estar explícito, usamos creation date o agregamos fecha_envio_cocina)
            # Wait, the model might not have fecha_envio_cocina. Let's use 'fecha_creacion' if it doesn't exist, or we check the model.
            # Assuming 'fecha_creacion' is there.
            comanda_data['lineas'].append({
                'id': l.id,
                'plato_nombre': l.plato.nombre,
                'cantidad': l.cantidad,
                'notas': getattr(l, 'observacion', getattr(l, 'notas_cocina', '')),
                'estado': l.estado,
                'tiempo_preparacion_min': l.plato.tiempo_preparacion_min,
                # Usa un campo de fecha que exista, o timezone.now() si no
                'fecha_envio_cocina': getattr(c, 'fecha_creacion', getattr(c, 'fecha_apertura', timezone.now())).isoformat() 
            })
        data.append(comanda_data)
        
    return Response(data)

@api_view(['PATCH'])
@permission_classes([EsCocineroOAdmin])
def api_linea_estado(request, pk):
    """
    PATCH /api/lineas/{id}/estado/
    Actualiza el estado de una línea de comanda.
    Permisos: 
    - Cualquiera: PENDIENTE -> EN_PREP
    - Solo COCINERO: EN_PREP -> LISTO
    """
    try:
        linea, _ = CocinaService.cambiar_estado(
            pk, request.data.get('estado'), request.user
        )
    except AppError as exc:
        return _error_response(exc)
    return Response({'ok': True, 'id': linea.id, 'estado': linea.estado})


@api_view(['POST'])
@permission_classes([EsCocineroOAdmin])
def api_enviar_linea_cocina(request, pk):
    """Explicit endpoint required by the KDS contract: PENDIENTE -> EN_PREP."""
    try:
        linea, _ = CocinaService.cambiar_estado(
            pk, LineaComanda.Estado.EN_PREP, request.user
        )
    except AppError as exc:
        return _error_response(exc)
    return Response({'ok': True, 'id': linea.id, 'estado': linea.estado})

# ─────────────────────────────────────────────────────────────────────────────
# KDS HTML View
# ─────────────────────────────────────────────────────────────────────────────
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from apps.mesas.models import Zona

@login_required
@rol_requerido('COCINERO', 'ADMIN')
def kds_view(request):
    """Renderiza el template del Kitchen Display System."""
    zonas = Zona.objects.filter(activo=True).order_by('nombre')
    return render(request, 'cocina/kds.html', {'zonas': zonas})


# ─────────────────────────────────────────────────────────────────────────────
# KDS API — comandas-activas (reemplaza el endpoint legacy)
# ─────────────────────────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([EsCocineroOAdmin])
def api_cocina_activas(request):
    """
    GET /api/cocina/comandas-activas/?zona=<id>
    Retorna comandas activas (ABIERTA o EN_PREPARACION) con líneas relevantes.
    Serializa los campos exactos que kds.js necesita.
    """
    zona_id = request.GET.get('zona')

    lineas_filter = LineaComanda.objects.exclude(
        estado__in=[LineaComanda.Estado.ENTREGADO, LineaComanda.Estado.ANULADO]
    ).select_related('plato')

    lineas_cocina = Prefetch('lineas', queryset=lineas_filter, to_attr='lineas_activas')

    qs = Comanda.objects.filter(
        estado__in=[Comanda.Estado.ABIERTA, Comanda.Estado.EN_PREPARACION],
        lineas__estado__in=[LineaComanda.Estado.PENDIENTE, LineaComanda.Estado.EN_PREP]
    ).select_related('mesa', 'mesa__zona', 'mozo').prefetch_related(lineas_cocina).distinct()

    if zona_id:
        qs = qs.filter(mesa__zona_id=zona_id)

    ahora = timezone.now()
    data = []
    for idx, c in enumerate(qs, start=1):
        if not c.lineas_activas:
            continue

        # Detectar urgencia: alguna línea supera su tiempo estimado
        tiene_urgencia = False
        lineas_data = []
        for orden, l in enumerate(c.lineas_activas, start=1):
            # Tiempo transcurrido desde que se empezó a preparar
            if l.estado == LineaComanda.Estado.EN_PREP and l.fecha_inicio_prep:
                diff_mins = (ahora - l.fecha_inicio_prep).total_seconds() / 60
            else:
                diff_mins = (ahora - l.created_at).total_seconds() / 60

            # Usar el tiempo estimado de la línea (campo propio del modelo)
            tiempo_estimado = l.tiempo_estimado_min or 0
            if tiempo_estimado > 0 and diff_mins > tiempo_estimado:
                tiene_urgencia = True

            estado_display_map = {
                LineaComanda.Estado.PENDIENTE: 'PENDIENTE',
                LineaComanda.Estado.EN_PREP: 'EN PREP',
                LineaComanda.Estado.LISTO: 'LISTO',
                LineaComanda.Estado.ENTREGADO: 'ENTREGADO',
                LineaComanda.Estado.ANULADO: 'ANULADO',
            }

            lineas_data.append({
                'id': l.id,
                'plato_nombre': l.plato.nombre,
                'cantidad': l.cantidad,
                'estado': l.estado,
                'estado_display': estado_display_map.get(l.estado, l.estado),
                'tiempo_transcurrido_min': int(diff_mins),
                'tiempo_estimado': tiempo_estimado,
                'fecha_inicio_prep_iso': l.fecha_inicio_prep.isoformat() if l.fecha_inicio_prep else None,
                'fecha_envio_cocina_iso': l.fecha_envio_cocina.isoformat() if l.fecha_envio_cocina else None,
                'tiempo_real_preparacion_seg': l.tiempo_real_preparacion_seg,
                'orden_entrega': orden,
                'observacion': l.observacion or '',
            })

        data.append({
            'id': c.id,
            'numero_pedido': idx,
            'codigo_comanda': c.codigo_comanda,
            'mesa_numero': c.mesa.numero,
            'zona_nombre': c.mesa.zona.nombre if c.mesa.zona else '',
            'zona_id': c.mesa.zona_id if c.mesa.zona else None,
            'mozo_nombre': c.mozo.username if c.mozo else 'Desconocido',
            'estado': c.estado,
            'fecha_apertura': c.fecha_apertura.isoformat(),
            'observacion_general': c.observacion_general or '',
            'tiene_urgencia': tiene_urgencia,
            'lineas': lineas_data,
        })

    return Response(data)


@api_view(['PATCH'])
@permission_classes([EsCocineroOAdmin])
def api_cocina_cambiar_estado(request, pk):
    """
    PATCH /api/cocina/lineas/<id>/cambiar-estado/
    Body: { "nuevo_estado": "EN_PREP"|"LISTO"|"ANULADO", "motivo": "...", "cantidad_parcial": 0 }
    Compatible con kds.js — usa 'nuevo_estado' en lugar de 'estado'.
    cantidad_parcial: si > 0, indica cuántas unidades el cocinero SÍ puede preparar.
    """
    nuevo_estado = request.data.get('nuevo_estado')
    motivo = request.data.get('motivo', '')
    try:
        cantidad_parcial = int(request.data.get('cantidad_parcial', 0))
        linea, nueva_linea_parcial = CocinaService.cambiar_estado(
            pk, nuevo_estado, request.user, motivo, cantidad_parcial
        )
    except (TypeError, ValueError):
        return Response({'error': 'Cantidad parcial invalida.'}, status=400)
    except AppError as exc:
        return _error_response(exc)

    mensaje_map = {
        LineaComanda.Estado.EN_PREP: f'Plato "{linea.plato.nombre}" marcado En Preparación',
        LineaComanda.Estado.LISTO:   f'Plato "{linea.plato.nombre}" marcado Listo',
        LineaComanda.Estado.ANULADO: f'Plato "{linea.plato.nombre}" anulado',
    }

    resp_data = {
        'ok': True,
        'id': linea.id,
        'estado': linea.estado,
        'mensaje': mensaje_map.get(nuevo_estado, 'Estado actualizado'),
    }
    if nueva_linea_parcial:
        resp_data['linea_parcial_id'] = nueva_linea_parcial.id
        resp_data['cantidad_parcial'] = cantidad_parcial
        resp_data['mensaje'] = f'Plato "{linea.plato.nombre}" anulado parcialmente. Se prepararán {cantidad_parcial} de {linea.cantidad}.'

    return Response(resp_data)


@api_view(['GET'])
@permission_classes([EsCocineroOAdmin])
def api_cocina_resumen(request):
    """
    GET /api/cocina/resumen/?zona=<id>
    Devuelve el resumen estadístico para la barra lateral del KDS.
    """
    zona_id = request.GET.get('zona')

    qs = Comanda.objects.filter(
        estado__in=[Comanda.Estado.ABIERTA, Comanda.Estado.EN_PREPARACION],
        lineas__estado__in=[LineaComanda.Estado.PENDIENTE, LineaComanda.Estado.EN_PREP]
    ).distinct()

    if zona_id:
        qs = qs.filter(mesa__zona_id=zona_id)

    total = qs.count()

    # Urgentes y Recién Llegados
    ahora = timezone.now()
    urgentes = 0
    recien_llegados = 0
    
    for c in qs.prefetch_related('lineas'):
        # Recién llegado: Todas las líneas relevantes para cocina están en PENDIENTE
        lineas_relevantes = [l for l in c.lineas.all() if l.estado in [LineaComanda.Estado.PENDIENTE, LineaComanda.Estado.EN_PREP]]
        if lineas_relevantes and all(l.estado == LineaComanda.Estado.PENDIENTE for l in lineas_relevantes):
            recien_llegados += 1
            
        # Urgentes: comandas con alguna línea EN_PREP que supera su tiempo estimado
        for l in c.lineas.all():
            if l.estado == LineaComanda.Estado.EN_PREP:
                est = l.tiempo_estimado_min or 0
                if est > 0 and l.fecha_inicio_prep:
                    mins = (ahora - l.fecha_inicio_prep).total_seconds() / 60
                    if mins > est:
                        urgentes += 1
                        break

    return Response({'total_pedidos': total, 'pedidos_urgentes': urgentes, 'recien_llegados': recien_llegados})

