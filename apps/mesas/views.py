"""
Vistas y API endpoints para la app mesas.

Endpoints API:
  GET /api/mesas/libres/         → Mesas con estado LIBRE agrupadas por piso
  GET /api/mesas/estado-actual/  → Estado de todas las mesas + detalle de comanda activa

Vistas HTML:
  GET /mesero/mesas/             → Plano de Mesas (Pantalla 2)
  GET /mesero/nueva-comanda/     → Toma de Pedidos (Pantalla 1)
"""
import json
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET
from django.contrib.auth.decorators import login_required

from .models import Mesa
from apps.comandas.models import Comanda, LineaComanda


# ─────────────────────────────────────────────────────────────────────────────
# VISTAS HTML
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def plano_mesas_view(request):
    """Pantalla 2: Plano visual de mesas con polling Alpine.js."""
    pisos = Mesa.Piso.choices   # Pasar los choices al template para los filtros
    return render(request, 'mesero/plano_mesas.html', {'pisos': pisos})


@login_required
def toma_pedidos_view(request):
    """Pantalla 1: Toma de pedidos / nueva comanda."""
    pisos = Mesa.Piso.choices
    return render(request, 'mesero/toma_pedidos.html', {'pisos': pisos})


# ─────────────────────────────────────────────────────────────────────────────
# API ENDPOINTS
# ─────────────────────────────────────────────────────────────────────────────

@require_GET
def api_mesas_libres(request):
    """
    GET /api/mesas/libres/
    Devuelve las mesas con estado=LIBRE, opcionalmente filtradas por piso.
    Query params: ?piso=PB
    """
    qs = Mesa.objects.filter(estado=Mesa.Estado.LIBRE)
    piso = request.GET.get('piso')
    if piso:
        qs = qs.filter(piso=piso)

    # Agrupar por piso para que Alpine pueda renderizar secciones
    pisos_dict: dict = {}
    for mesa in qs:
        label = mesa.get_piso_display()
        pisos_dict.setdefault(label, []).append({
            'id':        mesa.pk,
            'numero':    mesa.numero,
            'capacidad': mesa.capacidad,
            'piso':      mesa.piso,
            'piso_label': label,
        })

    return JsonResponse({'pisos': pisos_dict, 'total': qs.count()})


@require_GET
def api_estado_actual(request):
    """
    GET /api/mesas/estado-actual/
    Endpoint de polling (Alpine.js Pantalla 2).
    Devuelve el estado de TODAS las mesas.
    Si la mesa tiene una comanda abierta, incluye su detalle completo.
    """
    mesas_data = []

    for mesa in Mesa.objects.all():
        mesa_dict = {
            'id':         mesa.pk,
            'numero':     mesa.numero,
            'capacidad':  mesa.capacidad,
            'piso':       mesa.piso,
            'piso_label': mesa.get_piso_display(),
            'estado':     mesa.estado,
            'estado_label': mesa.get_estado_display(),
            'comanda':    None,
        }

        # Si la mesa está ocupada, adjuntar el detalle de la comanda activa
        if mesa.estado == Mesa.Estado.OCUPADA:
            comanda = (
                mesa.comandas
                .filter(estado=Comanda.Estado.ABIERTA)
                .prefetch_related('lineas__plato')
                .order_by('-fecha_apertura')
                .first()
            )
            if comanda:
                lineas = []
                for linea in comanda.lineas.all():
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

                mesa_dict['comanda'] = {
                    'id':              comanda.pk,
                    'fecha_apertura':  comanda.fecha_apertura.strftime('%H:%M'),
                    'mesero':          str(comanda.mesero) if comanda.mesero else 'N/A',
                    'notas':           comanda.notas,
                    'total':           str(comanda.total),
                    'lineas':          lineas,
                }

        mesas_data.append(mesa_dict)

    return JsonResponse({'mesas': mesas_data})
