"""
Vistas y API endpoints del módulo Caja (versión completa).

HTML:
  GET  /caja/apertura/              → apertura_caja_view
  GET  /caja/cobrar/                → cobrar_view
  GET  /caja/cierre/                → cierre_caja_view
  GET  /caja/boleta/<id>/           → descargar_boleta_view

API:
  POST /caja/api/abrir-turno/       → api_abrir_turno
  POST /caja/api/cerrar-turno/      → api_cerrar_turno
  GET  /caja/api/turno-activo/      → api_turno_activo
  POST /caja/api/pagar/<pk>/        → api_pagar_comanda (multi-pago)
  POST /caja/api/registrar-perdida/<pk>/  → api_registrar_perdida
  GET  /caja/api/historial/         → api_historial_pagos
"""
import json
import datetime
from itertools import groupby

from django.shortcuts import render, redirect
from django.http import JsonResponse, FileResponse
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db import models
from django.contrib import messages

from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import status

from apps.usuarios.decorators import rol_requerido
from apps.usuarios.permissions import EsCajeroOAdmin, EsMozoOAdmin
from apps.comandas.models import Comanda, LineaComanda
from .models import CajaTurno, MetodoPago, Pago
from apps.mesas.models import UnionMesas, Mesa
from .services import CajaService
from apps.core.exceptions import AppError, StockInsuficiente
from apps.inventario.services import InventarioService
from .utils import generar_pdf_boleta

# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _anotar_union_labels(comandas_list):
    """Anota cada comanda con union_label y capacidad_union si corresponde."""
    for c in comandas_list:
        c.union_label = c.mesa_label if c.mesas_adicionales.exists() else None
        c.capacidad_union = sum(m.capacidad for m in c.todas_las_mesas) if c.union_label else None

    uniones = {
        u.mesa_principal_id: u
        for u in UnionMesas.objects.filter(activa=True).prefetch_related('mesas_secundarias')
    }
    for c in comandas_list:
        if c.union_label:
            continue
        union = uniones.get(c.mesa_id)
        if union is None:
            for u in uniones.values():
                if c.mesa in u.mesas_secundarias.all():
                    union = u
                    break
        if union:
            nums = [str(union.mesa_principal.numero)] + [str(m.numero) for m in union.mesas_secundarias.all()]
            c.union_label = 'Mesa ' + ' + '.join(nums)
            c.capacidad_union = union.capacidad_total
        else:
            c.union_label = None
            c.capacidad_union = None


# ─────────────────────────────────────────────────────────────────────────────
# VISTAS HTML
# ─────────────────────────────────────────────────────────────────────────────

@login_required
@rol_requerido('CAJERO', 'ADMIN')
def apertura_caja_view(request):
    turno_activo = CajaTurno.objects.filter(estado=CajaTurno.Estado.ABIERTA).first()
    return render(request, 'caja/apertura.html', {
        'turno_activo': turno_activo,
        'puntos_caja': CajaTurno.PUNTO_CAJA_CHOICES,
    })


@login_required
@rol_requerido('CAJERO', 'ADMIN')
def cobrar_view(request):
    turno_activo = CajaTurno.objects.filter(estado=CajaTurno.Estado.ABIERTA).first()
    if not turno_activo:
        messages.warning(request, "Debes abrir un turno de caja antes de cobrar.")
        return redirect('caja_apertura')

    # Comandas listas para cobrar: SOLO las de mesas en estado POR_PAGAR
    # (el mesero presionó "Cobrar y Liberar", lo que cambia la mesa a POR_PAGAR)
    comandas_listas = list(
        Comanda.objects.filter(
            estado=Comanda.Estado.LISTA,
            mesa__estado=Mesa.Estado.POR_PAGAR
        )
        .select_related('mesa', 'mozo', 'mesa__zona')
        .prefetch_related('mesas_adicionales', 'lineas__plato', 'lineas__pagos')
    )

    _anotar_union_labels(comandas_listas)

    # Calcular total_pendiente para cada comanda (excluye líneas anuladas y ya pagadas)
    for c in comandas_listas:
        # Determinar qué líneas ya fueron pagadas en cobros previos usando prefetch cache
        lineas_ya_pagadas_ids = set()
        for l in c.lineas.all():
            if any(p.estado == Pago.Estado.PAGADO for p in l.pagos.all()):
                lineas_ya_pagadas_ids.add(l.id)

        lineas_activas = [l for l in c.lineas.all() if l.estado != LineaComanda.Estado.ANULADO]

        lineas_por_pagar = [l for l in lineas_activas if l.id not in lineas_ya_pagadas_ids]
        
        c.total_pendiente = sum(l.subtotal for l in lineas_por_pagar)
        
        # Serializar lineas para Alpine.js (selector de platos individuales con estado de pago)
        c.lineas_caja_json = json.dumps([{
            'id': l.id,
            'plato_nombre': l.plato.nombre,
            'cantidad': l.cantidad,
            'subtotal': float(l.subtotal),
            'estado': l.estado,
            'ya_pagado': l.id in lineas_ya_pagadas_ids,
        } for l in c.lineas.all()])

        c.total_pendiente = sum(l.subtotal for l in lineas_activas)
        # lineas_json ya es @property del modelo Comanda — no necesita reasignarse


    metodos_pago = MetodoPago.objects.filter(activo=True)

    return render(request, 'caja/cobrar.html', {
        'comandas': comandas_listas,
        'metodos_pago': metodos_pago,
        'turno_activo': turno_activo,
    })


@login_required
@rol_requerido('CAJERO', 'ADMIN')
def cierre_caja_view(request):
    turno_activo = CajaTurno.objects.filter(estado=CajaTurno.Estado.ABIERTA).first()
    if not turno_activo:
        return redirect('caja_apertura')

    # Resumen por método de pago
    resumen_pagos = []
    for metodo in MetodoPago.objects.filter(activo=True):
        total = Pago.objects.filter(
            caja_turno=turno_activo,
            metodo_pago=metodo,
            estado=Pago.Estado.PAGADO
        ).aggregate(total=models.Sum('monto'))['total'] or 0
        resumen_pagos.append({'nombre': metodo.nombre, 'total': float(total)})

    # Calcular Pérdidas
    perdidas_qs = Pago.objects.filter(
        caja_turno=turno_activo,
        estado=Pago.Estado.PERDIDA
    )
    total_perdidas = perdidas_qs.aggregate(total=models.Sum('monto'))['total'] or 0
    cantidad_perdidas = perdidas_qs.count()

    # Contar platos pendientes en cocina (PENDIENTE o EN_PREP)
    pendientes_cocina = LineaComanda.objects.filter(
        estado__in=[LineaComanda.Estado.PENDIENTE, LineaComanda.Estado.EN_PREP],
        comanda__estado__in=[Comanda.Estado.ABIERTA, Comanda.Estado.EN_PREPARACION, Comanda.Estado.LISTA]
    ).count()

    # Contar platos listos por servir (LISTO)
    pendientes_servicio = LineaComanda.objects.filter(
        estado=LineaComanda.Estado.LISTO,
        comanda__estado__in=[Comanda.Estado.ABIERTA, Comanda.Estado.EN_PREPARACION, Comanda.Estado.LISTA]
    ).count()

    # Contar comandas sin cobrar (ABIERTA, EN_PREPARACION, LISTA)
    comandas_no_cobradas = Comanda.objects.filter(
        estado__in=[Comanda.Estado.ABIERTA, Comanda.Estado.EN_PREPARACION, Comanda.Estado.LISTA]
    ).count()

    efectivo_esperado = float(turno_activo.saldo_inicial) + float(turno_activo.total_efectivo)
    cajero_turno_nombre = turno_activo.cajero.get_turno_display()

    return render(request, 'caja/cierre.html', {
        'turno': turno_activo,
        'resumen_pagos': resumen_pagos,
        'efectivo_esperado': efectivo_esperado,
        'total_perdidas': float(total_perdidas),
        'cantidad_perdidas': cantidad_perdidas,
        'cajero_turno_nombre': cajero_turno_nombre,
        'pendientes_cocina': pendientes_cocina,
        'pendientes_servicio': pendientes_servicio,
        'comandas_no_cobradas': comandas_no_cobradas,
    })


# Boleta disponible sin login para acceso por QR
def descargar_boleta_view(request, pago_id):
    """Genera y sirve el PDF de la boleta de venta."""
    try:
        pago = Pago.objects.select_related(
            'comanda', 'comanda__mesa', 'comanda__mozo', 'metodo_pago'
        ).get(pk=pago_id)
        qr_url = request.build_absolute_uri()
        buffer = generar_pdf_boleta(pago, qr_url=qr_url)
        return FileResponse(buffer, as_attachment=False, filename=f"boleta_{pago_id}.pdf")
    except Pago.DoesNotExist:
        messages.error(request, "El pago solicitado no existe.")
        return redirect('caja_cobrar')


# ─────────────────────────────────────────────────────────────────────────────
# API ENDPOINTS
# ─────────────────────────────────────────────────────────────────────────────

@api_view(['POST'])
@permission_classes([EsCajeroOAdmin])
def api_abrir_turno(request):
    """Abre un nuevo turno de caja con saldo inicial y punto de caja."""
    try:
        turno = CajaService.abrir_turno(request.data, request.user, request=request)
    except AppError as exc:
        return Response(exc.as_dict(), status=exc.status_code)
    return Response({'ok': True, 'codigo': turno.codigo_turno})


@api_view(['POST'])
@permission_classes([EsCajeroOAdmin])
def api_cerrar_turno(request):
    """Cierra el turno activo con arqueo físico opcional."""
    try:
        CajaService.cerrar_turno(request.data, request.user, request=request)
    except AppError as exc:
        return Response(exc.as_dict(), status=exc.status_code)
    return Response({'ok': True})


@api_view(['GET'])
def api_turno_activo(request):
    """
    Devuelve el estado del turno activo.
    Accesible por cualquier usuario autenticado (incluyendo MOZO).
    """
    turno = CajaTurno.objects.filter(estado=CajaTurno.Estado.ABIERTA).first()
    if not turno:
        return Response({'activo': False})

    return Response({
        'activo': True,
        'codigo': turno.codigo_turno,
        'cajero': turno.cajero.username,
        'punto_caja': turno.get_punto_caja_display() if hasattr(turno, 'get_punto_caja_display') else turno.punto_caja,
        'fecha_apertura': turno.fecha_apertura,
    })


@api_view(['POST'])
@permission_classes([EsCajeroOAdmin])
def api_pagar_comanda(request, pk):
    """
    POST /caja/api/pagar/<pk>/
    Body:
    {
        "pagos": [
            {"metodo_pago_id": 1, "monto": 50.00, "referencia": ""},
            {"metodo_pago_id": 2, "monto": 20.00, "referencia": "TXN123"}
        ],
        "linea_ids": [1, 2, 3],  // opcional — cobro parcial
        "observacion": ""
    }
    """
    pagos_data = request.data.get('pagos', [])
    linea_ids = request.data.get('linea_ids', None)
    observacion = request.data.get('observacion', '')

    # Compatibilidad legacy (un solo pago con metodo_pago_id + monto_recibido)
    if not pagos_data:
        metodo_id = request.data.get('metodo_pago_id')
        monto = request.data.get('monto_recibido', 0)
        referencia = request.data.get('referencia', '')
        if metodo_id and monto:
            pagos_data = [{'metodo_pago_id': metodo_id, 'monto': monto, 'referencia': referencia}]

    if not pagos_data:
        return Response({'error': 'Se requiere al menos un método de pago.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        pagos = CajaService.cobrar(
            comanda_id=pk,
            pagos_data=pagos_data,
            usuario=request.user,
            linea_ids=linea_ids,
            observacion=observacion,
            request=request,
        )
        return Response({
            'ok': True,
            'pago_ids': [p.id for p in pagos],
            'boleta_url': f'/caja/boleta/{pagos[0].id}/',
        })
    except AppError as e:
        if isinstance(e, StockInsuficiente):
            InventarioService.registrar_excepcion_stock(
                e, request.user, request=request
            )
        return Response(e.as_dict(), status=e.status_code)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([EsCajeroOAdmin])
def api_registrar_perdida(request, pk):
    """
    POST /caja/api/registrar-perdida/<pk>/
    Marca una comanda como pérdida (cliente no pagó).
    Body: { "observacion": "motivo..." }
    """
    observacion = request.data.get('observacion', '')
    try:
        pago = CajaService.registrar_perdida(
            comanda_id=pk,
            usuario=request.user,
            observacion=observacion,
            request=request,
        )
        return Response({'ok': True, 'pago_id': pago.id})
    except AppError as e:
        return Response(e.as_dict(), status=e.status_code)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([EsCajeroOAdmin])
def api_historial_pagos(request):
    """
    GET /caja/api/historial/
    Devuelve el historial de pagos agrupado por comanda con desglose expandible.
    """
    pagos = Pago.objects.select_related(
        'comanda', 'comanda__mesa', 'comanda__mesa__zona', 'metodo_pago'
    ).prefetch_related('lineas_pagadas__plato').all().order_by('-fecha_pago')

    if request.user.rol.nombre == 'CAJERO':
        hoy = timezone.localtime(timezone.now()).date()
        pagos = pagos.filter(fecha_pago__date=hoy)
    else:
        fecha_inicio_str = request.GET.get('fecha_inicio')
        fecha_fin_str = request.GET.get('fecha_fin')
        if fecha_inicio_str and fecha_fin_str:
            try:
                fi = datetime.datetime.strptime(fecha_inicio_str, '%Y-%m-%d').date()
                ff = datetime.datetime.strptime(fecha_fin_str, '%Y-%m-%d').date()
                pagos = pagos.filter(fecha_pago__date__gte=fi, fecha_pago__date__lte=ff)
            except ValueError:
                pass
        else:
            hoy = timezone.localtime(timezone.now()).date()
            pagos = pagos.filter(fecha_pago__date=hoy)

    # Agrupar por comanda (todas las transacciones/boletas de una misma orden)
    data = []
    grupos = {}
    pagos_list = list(pagos)

    for p in pagos_list:
        key = f"comanda_{p.comanda_id}"
        if key not in grupos:
            grupos[key] = []
        grupos[key].append(p)

    for idx, (key, group_pagos) in enumerate(grupos.items(), start=1):
        primer_pago = group_pagos[0]
        es_multi = len(group_pagos) > 1
        monto_total = sum(p.monto - p.vuelto for p in group_pagos)

        desglose_pagos = [
            {
                'pago_id': p.id,
                'metodo': p.metodo_pago.nombre,
                'monto': float(p.monto),
                'referencia': p.referencia or '',
                'estado': p.estado,
                'boleta_url': f'/caja/boleta/{p.id}/',
            }
            for p in group_pagos
        ]

        data.append({
            'orden': idx,
            'comanda_id': primer_pago.comanda_id,
            'fecha_pago': timezone.localtime(primer_pago.fecha_pago).strftime('%d/%m/%Y %H:%M'),
            'cliente': primer_pago.comanda.nombre_cliente or 'Público en General',
            'mesa': f"Mesa {primer_pago.comanda.mesa.numero} ({primer_pago.comanda.mesa.zona.nombre if primer_pago.comanda.mesa.zona else ''})",
            'comanda_codigo': primer_pago.comanda.codigo_comanda,
            'monto_total': float(monto_total),
            'cantidad_pagos': len(group_pagos),
            'es_multi': es_multi,
            'estado': primer_pago.estado,
            'desglose_pagos': desglose_pagos,
        })

    return Response({'ok': True, 'pagos': data})
