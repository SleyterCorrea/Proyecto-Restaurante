"""
Vistas y API endpoints para la app mesas.

Endpoints API:
  GET  /api/mesas/libres/              → Mesas con estado LIBRE agrupadas por piso (incluye grupos unidos)
  GET  /api/mesas/estado-actual/       → Estado de todas las mesas + detalle de comanda activa + uniones
  GET  /api/mesas/uniones/             → Lista de uniones activas
  POST /api/mesas/union/crear/         → Crea unión entre 2-3 mesas LIBRES (solo ADMIN)
  DELETE /api/mesas/union/<id>/disolver/ → Disuelve una unión (solo ADMIN)

Vistas HTML:
  GET /mesero/mesas/             → Plano de Mesas (Pantalla 2)
  GET /mesero/nueva-comanda/     → Toma de Pedidos (Pantalla 1)
"""
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET
from django.contrib.auth.decorators import login_required
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

from apps.usuarios.decorators import rol_requerido
from apps.usuarios.services import UsuarioService
from apps.core.exceptions import AppError

from .models import Mesa, Zona, UnionMesas
from .services import MesaService
from apps.comandas.models import Comanda, LineaComanda


ZONAS_INVALIDAS = ('ZVAL',)


def _zonas_activas_validas():
    return Zona.objects.filter(activo=True).exclude(nombre__iexact='ZVAL').order_by('id')


def _estado_visual_mesa(mesa, comanda_data):
    """
    Estado visual para el plano:
    - OCUPADA (rojo): aún hay ítems pendientes, en preparación o listos sin entregar.
    - ENTREGADO (amarillo): todos los ítems activos ya fueron entregados.
    """
    if mesa.estado != Mesa.Estado.OCUPADA or not comanda_data:
        return mesa.estado, mesa.get_estado_display()

    lineas = comanda_data.get('lineas', [])
    estados_activos = [l['estado'] for l in lineas if l['estado'] != LineaComanda.Estado.ANULADO]

    if estados_activos and all(e == LineaComanda.Estado.ENTREGADO for e in estados_activos):
        return 'ENTREGADO', 'Pedido Entregado'

    return mesa.estado, mesa.get_estado_display()


def _serializar_union(union):
    """Serializa una UnionMesas al dict que el frontend necesita."""
    if union is None:
        return None
    secundarias = list(union.mesas_secundarias.all())
    return {
        'id': union.pk,
        'capacidad_total': union.capacidad_total,
        'mesa_principal_id': union.mesa_principal_id,
        'mesa_ids': [union.mesa_principal_id] + [m.id for m in secundarias],
        'mesa_numeros': [union.mesa_principal.numero] + [m.numero for m in secundarias],
    }


# ─────────────────────────────────────────────────────────────────────────────
# VISTAS HTML
# ─────────────────────────────────────────────────────────────────────────────

@login_required
@rol_requerido('MOZO', 'ADMIN')
def plano_mesas_view(request):
    """Pantalla 2: Plano visual de mesas con polling Alpine.js."""
    zonas = [(z.id, z.nombre) for z in _zonas_activas_validas()]
    return render(request, 'mesero/plano_mesas.html', {'pisos': zonas})


@login_required
@rol_requerido('MOZO', 'ADMIN')
def toma_pedidos_view(request):
    """Pantalla 1: Toma de pedidos / nueva comanda."""
    zonas = [(z.id, z.nombre) for z in _zonas_activas_validas()]
    return render(request, 'mesero/toma_pedidos.html', {'pisos': zonas})


# ─────────────────────────────────────────────────────────────────────────────
# API ENDPOINTS — MESAS
# ─────────────────────────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_mesas_libres(request):
    """
    GET /api/mesas/libres/
    Devuelve las mesas con estado=LIBRE, opcionalmente filtradas por zona.
    Incluye grupos de mesas unidas como unidades seleccionables.
    Query params: ?piso=ID
    """
    qs = Mesa.objects.filter(
        estado=Mesa.Estado.LIBRE,
        activo=True,
        zona__activo=True,
    ).exclude(zona__nombre__iexact='ZVAL').select_related('zona')
    piso = request.GET.get('piso')
    if piso:
        qs = qs.filter(zona_id=piso)

    # Cargar uniones activas
    uniones = UnionMesas.objects.filter(activa=True).prefetch_related('mesas_secundarias')
    # Mapear mesa_id → union
    mesa_a_union = {}
    for u in uniones:
        mesa_a_union[u.mesa_principal_id] = u
        for sec in u.mesas_secundarias.all():
            mesa_a_union[sec.id] = u

    # Agrupar por piso. Las mesas secundarias de un grupo no aparecen solas.
    pisos_dict: dict = {}
    grupos_ya_agregados = set()  # evitar duplicar grupos

    for mesa in qs:
        label = mesa.zona.nombre if mesa.zona else 'Sin Zona'
        union = mesa_a_union.get(mesa.id)

        if union:
            # Si esta mesa pertenece a un grupo, representar el grupo una sola vez
            if union.pk in grupos_ya_agregados:
                continue
            # Solo mostrar el grupo si TODAS las mesas del grupo están LIBRES
            todas_libres = all(
                m.estado == Mesa.Estado.LIBRE
                for m in union.todas_las_mesas
            )
            if not todas_libres:
                continue
            grupos_ya_agregados.add(union.pk)
            secundarias = list(union.mesas_secundarias.all())
            pisos_dict.setdefault(label, []).append({
                'id':             union.mesa_principal.pk,
                'numero':         union.mesa_principal.numero,
                'capacidad':      union.capacidad_total,
                'piso':           union.mesa_principal.zona_id,
                'piso_label':     label,
                'es_grupo':       True,
                'union_id':       union.pk,
                'mesa_ids':       [union.mesa_principal.pk] + [m.pk for m in secundarias],
                'mesa_numeros':   [union.mesa_principal.numero] + [m.numero for m in secundarias],
                'label':          ' + '.join(
                    [f'Mesa {union.mesa_principal.numero}'] + [f'Mesa {m.numero}' for m in secundarias]
                ),
            })
        else:
            pisos_dict.setdefault(label, []).append({
                'id':        mesa.pk,
                'numero':    mesa.numero,
                'capacidad': mesa.capacidad,
                'piso':      mesa.zona_id,
                'piso_label': label,
                'es_grupo':  False,
                'union_id':  None,
                'mesa_ids':  [mesa.pk],
                'mesa_numeros': [mesa.numero],
                'label':     f'Mesa {mesa.numero}',
            })

    return JsonResponse({'pisos': pisos_dict, 'total': qs.count()})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_estado_actual(request):
    """
    GET /api/mesas/estado-actual/
    Endpoint de polling (Alpine.js Pantalla 2).
    Devuelve el estado de TODAS las mesas + datos de unión.
    """
    mesas_data = []

    # 1. Obtener todas las comandas abiertas con sus mesas adicionales y líneas
    comandas_activas = (
        Comanda.objects.filter(
            estado__in=[
                Comanda.Estado.ABIERTA,
                Comanda.Estado.EN_PREPARACION,
                Comanda.Estado.LISTA,
            ]
        )
        .select_related('mesa', 'mozo')
        .prefetch_related('mesas_adicionales', 'lineas__plato')
    )

    # 2. Mapear cada mesa (principal o adicional) a su comanda
    mesa_id_to_comanda = {}
    for c in comandas_activas:
        lineas = []
        for linea in c.lineas.all():
            lineas.append({
                'id':             linea.pk,
                'plato_id':       linea.plato.pk,
                'plato_nombre':   linea.plato.nombre,
                'cantidad':       linea.cantidad,
                'precio_unitario': str(linea.precio_unitario),
                'subtotal':       str(linea.subtotal),
                'estado':         linea.estado,
                'estado_label':   linea.get_estado_display(),
                'notas_cocina':   linea.notas_cocina,
            })

        comanda_data = {
            'id':              c.pk,
            'fecha_apertura':  c.fecha_apertura.strftime('%H:%M'),
            'mesero':          str(c.mesero) if c.mesero else 'N/A',
            'mesa_label':      c.mesa_label,
            'mesa_ids':        [mesa.id for mesa in c.todas_las_mesas],
            'mesa_numeros':    c.mesa_numeros,
            'nombre_cliente':  c.nombre_cliente or '',
            'notas':           c.notas,
            'total':           str(c.total),
            'lineas':          lineas,
        }

        mesa_id_to_comanda[c.mesa_id] = comanda_data
        for ma in c.mesas_adicionales.all():
            mesa_id_to_comanda[ma.id] = comanda_data

    # 3. Cargar todas las uniones activas
    uniones = UnionMesas.objects.filter(activa=True).prefetch_related('mesas_secundarias', 'mesa_principal')
    mesa_a_union = {}
    for u in uniones:
        mesa_a_union[u.mesa_principal_id] = u
        for sec in u.mesas_secundarias.all():
            mesa_a_union[sec.id] = u

    # 4. Construir la respuesta para todas las mesas
    for mesa in (
        Mesa.objects.filter(activo=True, zona__activo=True)
        .exclude(zona__nombre__iexact='ZVAL')
        .select_related('zona')
        .all()
    ):
        comanda_data = mesa_id_to_comanda.get(mesa.id)
        estado_visual, estado_label = _estado_visual_mesa(mesa, comanda_data)

        # Info de unión para esta mesa
        union = mesa_a_union.get(mesa.id)
        union_data = None
        if union:
            secundarias = list(union.mesas_secundarias.all())
            es_principal = (union.mesa_principal_id == mesa.id)
            union_data = {
                'id':               union.pk,
                'es_principal':     es_principal,
                'capacidad_total':  union.capacidad_total,
                'mesa_principal_id': union.mesa_principal_id,
                'mesa_principal_numero': union.mesa_principal.numero,
                'mesa_ids':         [union.mesa_principal_id] + [m.id for m in secundarias],
                'mesa_numeros':     [union.mesa_principal.numero] + [m.numero for m in secundarias],
            }

        mesa_dict = {
            'id':           mesa.pk,
            'numero':       mesa.numero,
            'capacidad':    union.capacidad_total if union else mesa.capacidad,
            'piso':         mesa.zona_id,
            'piso_label':   mesa.zona.nombre if mesa.zona else 'Sin Zona',
            'estado':       estado_visual,
            'estado_label': estado_label,
            'comanda':      comanda_data,
            'union':        union_data,
        }
        mesas_data.append(mesa_dict)

    # 5. Obtener IDs de platos inactivos o sin disponibilidad
    from apps.menu.models import Plato
    platos_inactivos = list(Plato.objects.filter(disponible=False).values_list('id', flat=True))

    return JsonResponse({
        'mesas': mesas_data,
        'platos_inactivos': platos_inactivos
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_mesas_list(request):
    """
    GET /api/mesas/lista/
    Retorna una lista simple de todas las mesas activas.
    """
    mesas = Mesa.objects.filter(
        activo=True, zona__activo=True
    ).exclude(zona__nombre__iexact='ZVAL').order_by('numero')
    data = [{
        'id': m.id,
        'numero': m.numero,
        'piso': m.zona.nombre if m.zona else '—'
    } for m in mesas]
    return JsonResponse(data, safe=False)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_mesa_crear(request):
    """
    POST /api/mesas/crear/
    Crea una nueva mesa. Solo ADMIN.
    """
    if request.user.rol.nombre != 'ADMIN':
        UsuarioService.registrar_acceso_denegado(
            request.user, request=request, recurso=request.path
        )
        return JsonResponse({'ok': False, 'error': 'No tenés permisos para realizar esta acción.'}, status=403)

    try:
        mesa = MesaService.crear(request.data)
        # La gestion de mesas pertenece al flujo operativo normal del restaurante,
        # no a la auditoria critica de riesgos. No se registra en AuditLog.

        return JsonResponse({
            'ok': True,
            'mesa': {
                'id': mesa.id,
                'numero': mesa.numero,
                'piso_label': mesa.zona.nombre
            }
        })
    except AppError as exc:
        return JsonResponse(exc.as_dict(), status=exc.status_code)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def api_mesa_eliminar(request, pk):
    """
    DELETE /api/mesas/eliminar/<pk>/
    Elimina una mesa o la desactiva si tiene historial. Solo ADMIN.
    """
    if request.user.rol.nombre != 'ADMIN':
        UsuarioService.registrar_acceso_denegado(
            request.user, request=request, recurso=request.path
        )
        return JsonResponse({'ok': False, 'error': 'No tenés permisos para realizar esta acción.'}, status=403)

    try:
        mesa = MesaService.desactivar(pk)
        # Operacion de mesas: flujo operativo normal, fuera de la auditoria critica.
        return JsonResponse({'ok': True, 'mensaje': 'Mesa eliminada correctamente.'})
    except AppError as exc:
        return JsonResponse(exc.as_dict(), status=exc.status_code)


# ─────────────────────────────────────────────────────────────────────────────
# API ENDPOINTS — UNIONES DE MESAS
# ─────────────────────────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_uniones_list(request):
    """
    GET /api/mesas/uniones/
    Lista todas las uniones de mesas activas.
    """
    uniones = UnionMesas.objects.filter(activa=True).prefetch_related('mesas_secundarias', 'mesa_principal')
    data = []
    for u in uniones:
        data.append(_serializar_union(u))
    return JsonResponse({'uniones': data})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_union_crear(request):
    """
    POST /api/mesas/union/crear/
    Crea una unión entre mesas. Solo ADMIN.
    Body: { "mesa_principal_id": 3, "mesa_secundaria_ids": [5] }

    Reglas:
    - Solo ADMIN puede crear uniones.
    - Todas las mesas deben estar LIBRES.
    - Máximo 3 mesas por unión (1 principal + 2 secundarias).
    - Una mesa no puede pertenecer a más de una unión activa.
    """
    if request.user.rol.nombre not in ['ADMIN', 'MOZO']:
        UsuarioService.registrar_acceso_denegado(
            request.user, request=request, recurso=request.path
        )
        return JsonResponse({'ok': False, 'error': 'Solo ADMIN o MOZO puede unir mesas.'}, status=403)

    try:
        union = MesaService.crear_union(request.data)
        # Union de mesas: flujo operativo normal, fuera de la auditoria critica.
        return JsonResponse({'ok': True, 'union': _serializar_union(union)})
    except AppError as exc:
        return JsonResponse(exc.as_dict(), status=exc.status_code)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def api_union_disolver(request, pk):
    """
    DELETE /api/mesas/union/<pk>/disolver/
    Disuelve una unión de mesas. Solo ADMIN.
    """
    if request.user.rol.nombre not in ['ADMIN', 'MOZO']:
        UsuarioService.registrar_acceso_denegado(
            request.user, request=request, recurso=request.path
        )
        return JsonResponse({'ok': False, 'error': 'Solo ADMIN o MOZO puede disolver uniones.'}, status=403)

    try:
        union = MesaService.disolver_union(pk)
        numeros = [mesa.numero for mesa in union.todas_las_mesas]
        # Disolucion de union de mesas: flujo operativo normal, sin auditoria critica.
        return JsonResponse({'ok': True, 'mensaje': f'Unión de mesas {numeros} disuelta correctamente.'})
    except AppError as exc:
        return JsonResponse(exc.as_dict(), status=exc.status_code)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_mesa_limpiada(request, pk):
    """
    POST /api/mesas/<pk>/limpiada/
    Cambia el estado de una mesa de LIMPIEZA a LIBRE.
    """
    if request.user.rol.nombre not in ['ADMIN', 'MOZO']:
        UsuarioService.registrar_acceso_denegado(
            request.user, request=request, recurso=request.path
        )
        return JsonResponse({'ok': False, 'error': 'Permiso denegado.'}, status=403)

    try:
        mesa = MesaService.marcar_limpiada(pk)
        # Cambio de estado de mesa: flujo operativo normal, fuera de la auditoria critica.
        return JsonResponse({'ok': True})
    except AppError as exc:
        return JsonResponse(exc.as_dict(), status=exc.status_code)
