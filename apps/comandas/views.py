"""
Vistas y API endpoints para la app comandas.

API Endpoints:
  POST  /api/comandas/crear/           → Crea Comanda + LineaComanda atómicamente
  PATCH /api/comandas/linea/<id>/editar/ → Edita una LineaComanda (ej. cancelada)
  POST  /api/mesas/<id>/liberar/       → Cierra comanda y libera la mesa
"""
import json
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction
from django.utils import timezone

from .models import Comanda, LineaComanda
from apps.mesas.models import Mesa
from apps.menu.models import Plato


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _parse_json_body(request) -> tuple[dict | list, None] | tuple[None, JsonResponse]:
    """Parsea el body JSON de la request. Devuelve (data, None) o (None, error_response)."""
    try:
        data = json.loads(request.body)
        return data, None
    except (json.JSONDecodeError, ValueError):
        return None, JsonResponse({'ok': False, 'error': 'JSON inválido'}, status=400)


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/comandas/crear/
# ─────────────────────────────────────────────────────────────────────────────

@csrf_exempt          # Alpine.js envía el CSRF token en el header; ajusta según tu config
@require_POST
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
    data, err = _parse_json_body(request)
    if err:
        return err

    # ── Validaciones básicas ──────────────────────────────────────────────────
    mesa_id = data.get('mesa_id')
    items   = data.get('items', [])

    if not mesa_id:
        return JsonResponse({'ok': False, 'error': 'Falta el campo mesa_id'}, status=400)
    if not items:
        return JsonResponse({'ok': False, 'error': 'El pedido no tiene ítems'}, status=400)

    # ── Obtener la mesa y verificar que esté libre ────────────────────────────
    try:
        mesa = Mesa.objects.get(pk=mesa_id)
    except Mesa.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'Mesa no encontrada'}, status=404)

    if mesa.estado != Mesa.Estado.LIBRE:
        return JsonResponse(
            {'ok': False, 'error': f'La mesa {mesa.numero} no está libre (estado: {mesa.get_estado_display()})'},
            status=409
        )

    # ── Bloque atómico: todo o nada ───────────────────────────────────────────
    try:
        with transaction.atomic():
            # 1. Crear la Comanda
            comanda = Comanda.objects.create(
                mesa   = mesa,
                mesero = request.user if request.user.is_authenticated else None,
                estado = Comanda.Estado.ABIERTA,
                notas  = data.get('notas', ''),
            )

            # 2. Crear las LineaComanda
            for item in items:
                plato_id = item.get('plato_id')
                cantidad = int(item.get('cantidad', 1))

                if not plato_id or cantidad < 1:
                    raise ValueError(f'Ítem inválido: {item}')

                plato = Plato.objects.get(pk=plato_id)   # Lanza si no existe → rollback

                LineaComanda.objects.create(
                    comanda         = comanda,
                    plato           = plato,
                    cantidad        = cantidad,
                    precio_unitario = plato.precio,       # Snapshot del precio actual
                    estado          = LineaComanda.Estado.PENDIENTE,
                    notas_cocina    = item.get('notas', ''),
                )

            # 3. Marcar la mesa como OCUPADA
            mesa.estado = Mesa.Estado.OCUPADA
            mesa.save(update_fields=['estado'])

    except Plato.DoesNotExist as e:
        return JsonResponse({'ok': False, 'error': f'Plato no encontrado: {e}'}, status=404)
    except (ValueError, KeyError) as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)

    return JsonResponse({
        'ok':         True,
        'comanda_id': comanda.pk,
        'redirect':   '/mesero/mesas/',
    }, status=201)


# ─────────────────────────────────────────────────────────────────────────────
# PATCH /api/comandas/linea/<linea_id>/editar/
# ─────────────────────────────────────────────────────────────────────────────

@csrf_exempt
@require_http_methods(['PATCH'])
def api_editar_linea(request, linea_id):
    """
    Edita una LineaComanda existente (típicamente una que fue cancelada).
    Permite cambiar: plato_id, cantidad, notas_cocina, estado.

    Body JSON:
    {
      "plato_id":    5,         (opcional) reemplaza el plato
      "cantidad":    2,         (opcional)
      "notas":       "...",     (opcional)
      "estado":      "PENDIENTE" (opcional)
    }
    """
    data, err = _parse_json_body(request)
    if err:
        return err

    try:
        linea = LineaComanda.objects.select_related('plato', 'comanda__mesa').get(pk=linea_id)
    except LineaComanda.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'Línea no encontrada'}, status=404)

    with transaction.atomic():
        if 'plato_id' in data:
            nuevo_plato = Plato.objects.get(pk=data['plato_id'])
            linea.plato           = nuevo_plato
            linea.precio_unitario = nuevo_plato.precio  # Actualizar precio
        if 'cantidad' in data:
            linea.cantidad = max(1, int(data['cantidad']))
        if 'notas' in data:
            linea.notas_cocina = data['notas']
        if 'estado' in data:
            estados_validos = [e[0] for e in LineaComanda.Estado.choices]
            if data['estado'] in estados_validos:
                linea.estado = data['estado']

        linea.save()

    return JsonResponse({
        'ok':      True,
        'linea_id': linea.pk,
        'nuevo_estado': linea.get_estado_display(),
    })


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/mesas/<mesa_id>/liberar/
# ─────────────────────────────────────────────────────────────────────────────

@csrf_exempt
@require_POST
def api_liberar_mesa(request, mesa_id):
    """
    Cierra la comanda activa de la mesa y la pone en estado LIBRE.
    Típicamente se llama al presionar "Liberar Mesa / Cobrar".
    """
    try:
        mesa = Mesa.objects.get(pk=mesa_id)
    except Mesa.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'Mesa no encontrada'}, status=404)

    with transaction.atomic():
        # Cerrar la comanda abierta
        comanda = (
            mesa.comandas
            .filter(estado=Comanda.Estado.ABIERTA)
            .order_by('-fecha_apertura')
            .first()
        )
        if comanda:
            comanda.estado        = Comanda.Estado.CERRADA
            comanda.fecha_cierre  = timezone.now()
            comanda.save(update_fields=['estado', 'fecha_cierre'])

        # Liberar la mesa
        mesa.estado = Mesa.Estado.LIBRE
        mesa.save(update_fields=['estado'])

    return JsonResponse({'ok': True, 'mesa_id': mesa_id, 'redirect': '/mesero/mesas/'})
