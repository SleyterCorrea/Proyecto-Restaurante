import csv
from django.shortcuts import render
from django.http import HttpResponse
from django.db.models import Sum, Count, Avg, F, Q
from django.db.models.functions import ExtractHour, ExtractWeekDay
from django.utils import timezone
from django.contrib.auth.decorators import login_required

from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import status

from apps.usuarios.permissions import EsCajeroOAdmin, EsAdmin
from apps.usuarios.decorators import rol_requerido
from apps.comandas.models import Comanda, LineaComanda
from apps.usuarios.models import AuditLog
from apps.caja.models import CajaTurno, Pago

# ─────────────────────────────────────────────────────────────────────────────
# HELPER
# ─────────────────────────────────────────────────────────────────────────────

def _calcular_tendencia(valor_actual, valor_anterior):
    """
    Devuelve el porcentaje de cambio entre dos valores.
    Retorna None si no hay valor anterior para comparar.
    """
    if valor_anterior is None or float(valor_anterior) == 0:
        return None
    diff = (float(valor_actual) - float(valor_anterior)) / float(valor_anterior) * 100
    return round(diff, 1)


# ─────────────────────────────────────────────────────────────────────────────
# VISTAS HTML
# ─────────────────────────────────────────────────────────────────────────────

@login_required
@rol_requerido('ADMIN', 'CAJERO')
def admin_reportes(request):
    """Vista principal de reportes gráficos."""
    return render(request, 'admin_panel/reportes.html')

@login_required
@rol_requerido('ADMIN')
def admin_inventario(request):
    return render(request, 'admin_panel/inventario.html')

@login_required
@rol_requerido('ADMIN')
def admin_recetas(request):
    return render(request, 'admin_panel/recetas.html')

@login_required
@rol_requerido('ADMIN')
def admin_menu(request):
    return render(request, 'admin_panel/menu.html')

@login_required
@rol_requerido('ADMIN', 'CAJERO')
def admin_dashboard(request):
    return render(request, 'admin_panel/reportes.html')

@login_required
@rol_requerido('ADMIN')
def admin_auditoria(request):
    return render(request, 'admin_panel/auditoria.html')


# ─────────────────────────────────────────────────────────────────────────────
# API ENDPOINTS
# ─────────────────────────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([EsCajeroOAdmin])
def api_ventas_turno(request):
    """
    Obtiene los KPIs del turno de caja activo, incluyendo tendencia
    comparada contra el turno anterior cerrado.
    """
    turno = CajaTurno.objects.filter(estado=CajaTurno.Estado.ABIERTA).first()
    if not turno:
        return Response({'error': 'No hay turno activo'}, status=400)

    mesa = request.GET.get('mesa')

    # ── Turno anterior para tendencias ──
    turno_anterior = CajaTurno.objects.filter(
        estado=CajaTurno.Estado.CERRADA
    ).order_by('-fecha_cierre').first()

    # Filtro base para las comandas del turno
    comandas_turno = Comanda.objects.filter(pagos__caja_turno=turno, estado=Comanda.Estado.COBRADA).distinct()
    comandas_ant = Comanda.objects.filter(pagos__caja_turno=turno_anterior, estado=Comanda.Estado.COBRADA).distinct() if turno_anterior else None

    if mesa:
        comandas_turno = comandas_turno.filter(mesa__numero=mesa)
        if comandas_ant:
            comandas_ant = comandas_ant.filter(mesa__numero=mesa)

    cant_comandas = comandas_turno.count()
    cant_ant = comandas_ant.count() if comandas_ant else None

    total_ventas = comandas_turno.aggregate(res=Sum('total'))['res'] or 0
    total_ant = comandas_ant.aggregate(res=Sum('total'))['res'] or 0 if comandas_ant else None

    ticket_promedio = float(total_ventas / cant_comandas) if cant_comandas > 0 else 0
    ticket_ant = (float(total_ant / cant_ant)
                  if comandas_ant and cant_ant and cant_ant > 0 else None)

    # Tiempo promedio de preparación (en minutos)
    base_lineas_turno = LineaComanda.objects.filter(
        comanda__in=comandas_turno,
        fecha_inicio_prep__isnull=False,
        fecha_listo__isnull=False
    ).exclude(estado=LineaComanda.Estado.ANULADO)

    tiempo_prep = base_lineas_turno.annotate(
        duracion=(F('fecha_listo') - F('fecha_inicio_prep'))
    ).aggregate(avg_time=Avg('duracion'))['avg_time']

    tiempo_min = (tiempo_prep.total_seconds() / 60) if tiempo_prep else 0

    tiempo_ant = None
    if comandas_ant:
        tp_ant = LineaComanda.objects.filter(
            comanda__in=comandas_ant,
            fecha_inicio_prep__isnull=False,
            fecha_listo__isnull=False
        ).exclude(estado=LineaComanda.Estado.ANULADO).annotate(
            duracion=(F('fecha_listo') - F('fecha_inicio_prep'))
        ).aggregate(avg_time=Avg('duracion'))['avg_time']
        tiempo_ant = (tp_ant.total_seconds() / 60) if tp_ant else None

    return Response({
        'total_ventas': float(total_ventas),
        'cant_comandas': cant_comandas,
        'ticket_promedio': round(ticket_promedio, 2),
        'tiempo_promedio_prep': round(tiempo_min, 1),
        # ── Tendencias ──
        'tendencia_ventas': _calcular_tendencia(total_ventas, total_ant),
        'tendencia_comandas': _calcular_tendencia(cant_comandas, cant_ant),
        'tendencia_ticket': _calcular_tendencia(ticket_promedio, ticket_ant),
        'tendencia_tiempo': _calcular_tendencia(tiempo_min, tiempo_ant),
    })


@api_view(['GET'])
@permission_classes([EsCajeroOAdmin])
def api_top_platos(request):
    """
    Obtiene el ranking de los 5 platos más vendidos en el turno actual.
    Incluye el total del turno para calcular los anchos de barra.
    """
    limite = int(request.GET.get('limite', 5))
    mesa = request.GET.get('mesa')
    turno = CajaTurno.objects.filter(estado=CajaTurno.Estado.ABIERTA).first()

    if not turno:
        return Response([])

    # Solo líneas activas de comandas cobradas del turno.
    base_lineas = LineaComanda.objects.filter(
        comanda__pagos__caja_turno=turno,
        comanda__estado=Comanda.Estado.COBRADA,
    ).exclude(
        estado=LineaComanda.Estado.ANULADO
    )

    if mesa:
        base_lineas = base_lineas.filter(comanda__mesa__numero=mesa)

    qs = base_lineas.values('plato_id', 'plato__nombre').annotate(
        cantidad=Sum('cantidad'),
    ).order_by('-cantidad')[:limite]

    data = list(qs)
    max_cantidad = data[0]['cantidad'] if data else 1

    weekday_es = {
        1: 'Domingo',
        2: 'Lunes',
        3: 'Martes',
        4: 'Miércoles',
        5: 'Jueves',
        6: 'Viernes',
        7: 'Sábado',
    }

    for item in data:
        item['porcentaje'] = round(item['cantidad'] / max_cantidad * 100)
        plato_id = item.get('plato_id')

        # Hora pico: hora con mayor cantidad vendida (basado en fecha de pago).
        # Si hay múltiples pagos por comanda (poco común), tomamos el agrupado por hora igualmente.
        pico_hora = base_lineas.filter(plato_id=plato_id).annotate(
            hora=ExtractHour('comanda__pagos__fecha_pago')
        ).values('hora').annotate(
            cantidad=Sum('cantidad')
        ).order_by('-cantidad', 'hora').first()

        item['hora_pico'] = (pico_hora['hora'] if pico_hora and pico_hora['hora'] is not None else None)

        # Día pico: día de semana con mayor cantidad vendida (basado en fecha de pago).
        pico_dia = base_lineas.filter(plato_id=plato_id).annotate(
            dia=ExtractWeekDay('comanda__pagos__fecha_pago')
        ).values('dia').annotate(
            cantidad=Sum('cantidad')
        ).order_by('-cantidad', 'dia').first()

        dia_num = (pico_dia['dia'] if pico_dia and pico_dia['dia'] is not None else None)
        item['dia_pico'] = weekday_es.get(dia_num) if dia_num else None

    return Response(data)


@api_view(['GET'])
@permission_classes([EsCajeroOAdmin])
def api_ventas_por_hora(request):
    """
    Obtiene el acumulado de ventas agrupado por hora para el gráfico de líneas.
    """
    turno = CajaTurno.objects.filter(estado=CajaTurno.Estado.ABIERTA).first()
    mesa = request.GET.get('mesa')

    pago_filter = Q(caja_turno=turno)
    if mesa:
        pago_filter &= Q(comanda__mesa__numero=mesa)

    qs = Pago.objects.filter(
        pago_filter
    ).annotate(
        hora=ExtractHour('fecha_pago')
    ).values('hora').annotate(
        total=Sum('monto')
    ).order_by('hora')

    return Response(list(qs))


@api_view(['GET'])
@permission_classes([EsCajeroOAdmin])
def api_ventas_historial(request):
    """
    Devuelve el historial detallado de todas las comandas cobradas
    en el turno activo, con soporte de búsqueda por código o mesa.
    Incluye el desglose de productos por comanda.
    """
    turno = CajaTurno.objects.filter(estado=CajaTurno.Estado.ABIERTA).first()
    if not turno:
        return Response({'results': []})

    search = request.GET.get('search', '').strip()
    mesa = request.GET.get('mesa', '').strip()
    fecha = request.GET.get('fecha', '').strip()  # YYYY-MM-DD (exacta)
    mes = request.GET.get('mes', '').strip()      # YYYY-MM (mes completo)

    comandas_qs = Comanda.objects.filter(
        pagos__caja_turno=turno,
        estado=Comanda.Estado.COBRADA,
    ).distinct().select_related('mesa', 'mozo').prefetch_related(
        'lineas__plato', 'pagos__metodo_pago'
    ).order_by('-fecha_cierre')

    # Filtros: búsqueda (código o mesa), mesa exacta, y fecha/mes por fecha de pago.
    filtros = Q()
    if search:
        # Si el usuario escribe solo un número, asumimos que está buscando una mesa EXACTA.
        # Esto evita que "5" devuelva mesas como "15".
        if search.isdigit():
            filtros &= Q(mesa__numero=int(search))
        else:
            filtros &= (Q(codigo_comanda__icontains=search) | Q(mesa__numero__icontains=search))
    if mesa:
        # El filtro de mesa debe ser exacto cuando es un número.
        if mesa.isdigit():
            filtros &= Q(mesa__numero=int(mesa))
        else:
            filtros &= Q(mesa__numero__icontains=mesa)

    if fecha:
        # Fecha exacta (día)
        try:
            dt = timezone.datetime.strptime(fecha, '%Y-%m-%d').date()
            filtros &= Q(pagos__fecha_pago__date=dt)
        except ValueError:
            pass

    if mes:
        # Mes completo (YYYY-MM)
        try:
            dtm = timezone.datetime.strptime(mes, '%Y-%m').date()
            filtros &= Q(pagos__fecha_pago__year=dtm.year, pagos__fecha_pago__month=dtm.month)
        except ValueError:
            pass

    if filtros:
        comandas_qs = comandas_qs.filter(filtros).distinct()

    TAX_RATE = 0.10  # IGV 10%

    results = []
    for c in comandas_qs:
        # Concatenar líneas no anuladas: "2x Lomo Saltado, 1x Inca Kola"
        lineas_activas = c.lineas.exclude(estado=LineaComanda.Estado.ANULADO)
        detalle = ', '.join(
            f"{l.cantidad}x {l.plato.nombre}" for l in lineas_activas
        )

        pago = c.pagos.filter(caja_turno=turno).order_by('-fecha_pago').first()
        bruto = float(c.total)
        impuesto = round(bruto * TAX_RATE, 2)
        neto = round(bruto - impuesto, 2)

        results.append({
            'id': c.id,
            'codigo': c.codigo_comanda,
            # En historial debe registrarse la fecha/hora real del registro de venta (pago).
            'fecha': pago.fecha_pago.strftime('%Y-%m-%d %H:%M') if pago and pago.fecha_pago else '—',
            'mesa': str(c.mesa.numero),
            'mozo': c.mozo.username,
            'detalle': detalle or '—',
            'bruto': bruto,
            'impuesto': impuesto,
            'neto': neto,
            'metodo': pago.metodo_pago.nombre if pago else 'N/A',
            'estado': c.estado,
        })

    return Response({'results': results})


@api_view(['GET'])
@permission_classes([EsCajeroOAdmin])
def api_exportar_csv(request):
    """
    Genera y descarga un archivo CSV con el detalle de todas las comandas cobradas en el turno.
    """
    turno = CajaTurno.objects.filter(estado=CajaTurno.Estado.ABIERTA).first()
    if not turno:
        return Response({'error': 'No hay turno activo'}, status=400)

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="reporte_ventas_{turno.codigo_turno}.csv"'

    writer = csv.writer(response)
    writer.writerow(['Codigo', 'Mesa', 'Mozo', 'Apertura', 'Cierre', 'Total Bruto', 'Impuesto (10%)', 'Neto', 'Metodo Pago'])

    TAX_RATE = 0.10
    comandas = Comanda.objects.filter(
        pagos__caja_turno=turno
    ).distinct().select_related('mesa', 'mozo')

    for c in comandas:
        pago = c.pagos.filter(caja_turno=turno).first()
        bruto = float(c.total)
        impuesto = round(bruto * TAX_RATE, 2)
        neto = round(bruto - impuesto, 2)
        writer.writerow([
            c.codigo_comanda,
            c.mesa.numero,
            c.mozo.username,
            c.fecha_apertura.strftime('%Y-%m-%d %H:%M'),
            c.fecha_cierre.strftime('%Y-%m-%d %H:%M') if c.fecha_cierre else '',
            bruto,
            impuesto,
            neto,
            pago.metodo_pago.nombre if pago else 'N/A'
        ])

    return response

@api_view(['GET'])
@permission_classes([EsAdmin])
def api_auditoria_logs(request):
    """
    Lista los registros de auditoría con filtros.
    """
    search = request.GET.get('search', '').strip()
    entidad = request.GET.get('entidad', '').strip()
    accion = request.GET.get('accion', '').strip()
    
    logs = AuditLog.objects.all().select_related('usuario').order_by('-fecha_evento')
    
    if search:
        logs = logs.filter(
            Q(usuario__username__icontains=search) |
            Q(detalle_nuevo__icontains=search) |
            Q(detalle_anterior__icontains=search)
        )
    
    if entidad:
        logs = logs.filter(entidad=entidad)
    
    if accion:
        logs = logs.filter(accion=accion)
        
    data = []
    for log in logs[:500]: # Limitar a los últimos 500 para performance
        data.append({
            'id': log.id,
            'fecha': log.fecha_evento.strftime('%Y-%m-%d %H:%M:%S'),
            'usuario': log.usuario.username,
            'accion': log.accion,
            'entidad': log.entidad,
            'entidad_id': log.entidad_id,
            'detalle_anterior': log.detalle_anterior,
            'detalle_nuevo': log.detalle_nuevo,
            'ip': log.ip
        })
        
    return Response(data)
