import csv
from django.shortcuts import render
from django.http import HttpResponse
from django.db.models import Sum, Count, Avg, F, Q, Max
from django.db.models.functions import ExtractHour, ExtractWeekDay
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.views.decorators.cache import never_cache

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
    from apps.usuarios.models import Usuario
    cajeros = Usuario.objects.filter(rol__nombre__in=['ADMIN', 'CAJERO'], is_active=True)
    return render(request, 'admin_panel/reportes.html', {'cajeros': cajeros})

@never_cache
@login_required
@rol_requerido('ADMIN')
def admin_inventario(request):
    import json
    from apps.inventario.models import Insumo, UnidadMedida
    from apps.inventario.serializers import InsumoSerializer, UnidadMedidaSerializer

    insumos = Insumo.objects.filter(activo=True).select_related('unidad_medida').order_by('nombre')
    unidades = UnidadMedida.objects.filter(activo=True).order_by('nombre')

    insumos_data = InsumoSerializer(insumos, many=True).data
    unidades_data = UnidadMedidaSerializer(unidades, many=True).data

    return render(request, 'admin_panel/inventario.html', {
        'insumos_json': json.dumps(list(insumos_data)),
        'unidades_json': json.dumps(list(unidades_data)),
        # Necesario para el {% for u in unidades %} del <select> en el modal Django server-side
        'unidades': unidades,
    })

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
    from apps.usuarios.models import Usuario
    cajeros = Usuario.objects.filter(rol__nombre__in=['ADMIN', 'CAJERO'], is_active=True)
    return render(request, 'admin_panel/reportes.html', {'cajeros': cajeros})

@login_required
@rol_requerido('ADMIN')
def admin_auditoria(request):
    return render(request, 'admin_panel/auditoria.html')


# ─────────────────────────────────────────────────────────────────────────────
# API ENDPOINTS
# ─────────────────────────────────────────────────────────────────────────────

def _get_base_pagos(request):
    """
    Retorna los pagos filtrados según los parámetros de consulta globales.
    Si no se especifican filtros temporales (fecha, mes, anio), se limita
    por defecto al turno activo o al último turno registrado para evitar
    mostrar todo el historial de la base de datos.
    """
    cajero_id = request.GET.get('cajero')
    turno_filtro = request.GET.get('turno')
    fecha_exacta = request.GET.get('fecha')
    mes = request.GET.get('mes')
    anio = request.GET.get('anio')
    solo_perdidas = request.GET.get('solo_perdidas')
    mesa = request.GET.get('mesa')
    estado_pago = request.GET.get('estado_pago')
    
    tiene_filtros_fecha = any([fecha_exacta, mes, anio])
    tiene_filtros = any([cajero_id, turno_filtro, fecha_exacta, mes, anio, solo_perdidas, mesa, estado_pago])
    
    if tiene_filtros_fecha:
        base = Pago.objects.all()
        if fecha_exacta:
            try:
                dt = timezone.datetime.strptime(fecha_exacta, '%Y-%m-%d').date()
                base = base.filter(fecha_pago__date=dt)
            except ValueError:
                pass
        else:
            if anio:
                base = base.filter(fecha_pago__year=int(anio))
            if mes:
                base = base.filter(fecha_pago__month=int(mes))
    else:
        # Si no hay filtros de fecha, acotamos por el turno activo o el último registrado
        turno_activo = CajaTurno.objects.filter(estado=CajaTurno.Estado.ABIERTA).first()
        if turno_activo:
            base = Pago.objects.filter(caja_turno=turno_activo)
        else:
            ultimo = CajaTurno.objects.order_by('-fecha_apertura').first()
            if ultimo:
                base = Pago.objects.filter(caja_turno=ultimo)
            else:
                base = Pago.objects.none()
                
    # Aplicar filtros no temporales de forma acumulativa y estricta
    if cajero_id:
        base = base.filter(caja_turno__cajero_id=cajero_id)
        
    if turno_filtro:
        base = base.filter(caja_turno__cajero__turno=turno_filtro)
        
    if solo_perdidas == 'true' or estado_pago == 'PERDIDAS':
        base = base.filter(estado=Pago.Estado.PERDIDA)
    elif estado_pago == 'COBRADOS':
        base = base.filter(estado=Pago.Estado.PAGADO)
        
    if mesa:
        base = base.filter(comanda__mesa__numero=mesa)
        
    return base, tiene_filtros

@api_view(['GET'])
@permission_classes([EsCajeroOAdmin])
def api_ventas_turno(request):
    """
    Obtiene los KPIs filtrados o del turno de caja activo,
    incluyendo tendencias si no se aplican filtros globales.
    """
    base_pagos, tiene_filtros = _get_base_pagos(request)

    # 1. Ventas Totales (exitosas)
    ventas_exitosas = base_pagos.filter(estado=Pago.Estado.PAGADO)
    total_ventas = ventas_exitosas.aggregate(res=Sum('monto'))['res'] or 0

    # 2. Cantidad de Comandas Cobradas
    comanda_ids = base_pagos.values_list('comanda_id', flat=True).distinct()
    cant_comandas = base_pagos.filter(estado=Pago.Estado.PAGADO).values('comanda').distinct().count()

    # 3. Total Pérdidas
    total_perdidas = base_pagos.filter(estado=Pago.Estado.PERDIDA).aggregate(res=Sum('monto'))['res'] or 0

    # 4. Tiempo Máximo de Preparación (Minutos)
    lineas = LineaComanda.objects.filter(
        comanda_id__in=comanda_ids,
        fecha_inicio_prep__isnull=False,
        fecha_listo__isnull=False
    ).exclude(estado=LineaComanda.Estado.ANULADO)

    tiempo_max = 0
    if lineas.exists():
        duraciones = lineas.annotate(
            duracion=(F('fecha_listo') - F('fecha_inicio_prep'))
        )
        max_duracion = duraciones.aggregate(max_time=Max('duracion'))['max_time']
        if max_duracion:
            tiempo_max = max_duracion.total_seconds() / 60

    # Tendencias: Solo calculadas si no se aplican filtros globales (para el turno activo actual)
    total_ant = None
    cant_ant = None
    perdidas_ant = None
    tiempo_ant = None

    if not tiene_filtros:
        # Buscamos el turno anterior
        turno_anterior = CajaTurno.objects.filter(
            estado=CajaTurno.Estado.CERRADA
        ).order_by('-fecha_cierre').first()

        if turno_anterior:
            pagos_ant = Pago.objects.filter(caja_turno=turno_anterior)
            
            # Ventas ant
            total_ant = pagos_ant.filter(estado=Pago.Estado.PAGADO).aggregate(res=Sum('monto'))['res'] or 0
            
            # Comandas ant
            cant_ant = pagos_ant.filter(estado=Pago.Estado.PAGADO).values('comanda').distinct().count()
            
            # Pérdidas ant
            perdidas_ant = pagos_ant.filter(estado=Pago.Estado.PERDIDA).aggregate(res=Sum('monto'))['res'] or 0
            
            # Tiempo ant
            comandas_ant_ids = pagos_ant.values_list('comanda_id', flat=True).distinct()
            lineas_ant = LineaComanda.objects.filter(
                comanda_id__in=comandas_ant_ids,
                fecha_inicio_prep__isnull=False,
                fecha_listo__isnull=False
            ).exclude(estado=LineaComanda.Estado.ANULADO)
            
            if lineas_ant.exists():
                duraciones_ant = lineas_ant.annotate(
                    duracion=(F('fecha_listo') - F('fecha_inicio_prep'))
                )
                max_duracion_ant = duraciones_ant.aggregate(max_time=Max('duracion'))['max_time']
                if max_duracion_ant:
                    tiempo_ant = max_duracion_ant.total_seconds() / 60

    # Retornar los KPIs
    return Response({
        'total_ventas': float(total_ventas),
        'cant_comandas': cant_comandas,
        'total_perdidas': float(total_perdidas),
        'tiempo_maximo_prep': round(tiempo_max, 1),
        # ── Tendencias ──
        'tendencia_ventas': _calcular_tendencia(total_ventas, total_ant) if total_ant is not None else None,
        'tendencia_comandas': _calcular_tendencia(cant_comandas, cant_ant) if cant_ant is not None else None,
        'tendencia_perdidas': _calcular_tendencia(total_perdidas, perdidas_ant) if perdidas_ant is not None else None,
        'tendencia_tiempo': _calcular_tendencia(tiempo_max, tiempo_ant) if tiempo_ant is not None else None,
    })


@api_view(['GET'])
@permission_classes([EsCajeroOAdmin])
def api_top_platos(request):
    """
    Obtiene el ranking de platos más vendidos y menos vendidos,
    así como la distribución por niveles de rotación aplicando filtros globales.
    """
    base_pagos, _ = _get_base_pagos(request)
    
    # Solo consideramos comandas cobradas exitosamente (excluyendo pérdidas de las estadísticas de rotación)
    comandas_exitosas = base_pagos.filter(estado=Pago.Estado.PAGADO).values_list('comanda_id', flat=True)
    
    base_lineas = LineaComanda.objects.filter(
        comanda_id__in=comandas_exitosas
    ).exclude(estado=LineaComanda.Estado.ANULADO)

    qs_all = base_lineas.values('plato_id', 'plato__nombre').annotate(
        cantidad=Sum('cantidad'),
    ).order_by('-cantidad')

    top_platos = list(qs_all[:5])
    peores_platos = list(qs_all.order_by('cantidad')[:5])
    
    max_cantidad = top_platos[0]['cantidad'] if top_platos else 1
    
    weekday_es = {
        1: 'Domingo',
        2: 'Lunes',
        3: 'Martes',
        4: 'Miércoles',
        5: 'Jueves',
        6: 'Viernes',
        7: 'Sábado',
    }

    for item in top_platos:
        item['porcentaje'] = round(item['cantidad'] / max_cantidad * 100) if max_cantidad > 0 else 0
        plato_id = item.get('plato_id')

        # Hora pico: hora con mayor cantidad vendida
        pico_hora = base_lineas.filter(plato_id=plato_id).annotate(
            hora=ExtractHour('comanda__pagos__fecha_pago')
        ).values('hora').annotate(
            cantidad_hora=Sum('cantidad')
        ).order_by('-cantidad_hora', 'hora').first()

        item['hora_pico'] = (pico_hora['hora'] if pico_hora and pico_hora['hora'] is not None else None)

        # Día pico
        pico_dia = base_lineas.filter(plato_id=plato_id).annotate(
            dia=ExtractWeekDay('comanda__pagos__fecha_pago')
        ).values('dia').annotate(
            cantidad_dia=Sum('cantidad')
        ).order_by('-cantidad_dia', 'dia').first()

        dia_num = (pico_dia['dia'] if pico_dia and pico_dia['dia'] is not None else None)
        item['dia_pico'] = weekday_es.get(dia_num) if dia_num else None

    # Distribución de rotación (Alta, Media, Baja) y clasificación detallada de platos
    from apps.menu.models import Plato
    from django.db.models import Value, IntegerField

    platos_alta = []
    platos_media = []
    platos_baja_rotacion = []

    # Platos que se han vendido en el periodo filtrado
    for item in qs_all:
        qty = item['cantidad']
        item['porcentaje'] = round(item['cantidad'] / max_cantidad * 100) if max_cantidad > 0 else 0
        if qty >= max_cantidad * 0.6:
            platos_alta.append(item)
        elif qty >= max_cantidad * 0.2:
            platos_media.append(item)
        else:
            platos_baja_rotacion.append(item)

    # Identificar platos activos que NO se vendieron en absoluto durante este periodo (0 ventas)
    platos_vendidos_ids = [item['plato_id'] for item in qs_all]
    platos_no_vendidos = list(Plato.objects.filter(activo=True).exclude(id__in=platos_vendidos_ids).values('id', 'nombre'))
    
    platos_no_vendidos_mapped = []
    for p in platos_no_vendidos:
        platos_no_vendidos_mapped.append({
            'plato_id': p['id'],
            'plato__nombre': p['nombre'],
            'cantidad': 0,
            'porcentaje': 0,
            'hora_pico': None,
            'dia_pico': None
        })

    # Platos Rezagados/Baja demanda incluye los que se vendieron poco + los que NO se vendieron nada (0 uds)
    platos_baja = platos_no_vendidos_mapped + platos_baja_rotacion

    alta_count = len(platos_alta)
    media_count = len(platos_media)
    baja_count = len(platos_baja)

    return Response({
        'top_platos': top_platos,
        'peores_platos': peores_platos,
        'distribucion': {
            'alta': alta_count,
            'media': media_count,
            'baja': baja_count,
        },
        'categorizados': {
            'alta': platos_alta,
            'media': platos_media,
            'baja': platos_baja,
        }
    })


@api_view(['GET'])
@permission_classes([EsCajeroOAdmin])
def api_ventas_por_hora(request):
    """
    Obtiene el acumulado de ventas agrupado por hora aplicando filtros globales.
    """
    base_pagos, _ = _get_base_pagos(request)
    
    qs = base_pagos.filter(
        estado=Pago.Estado.PAGADO
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
    Devuelve el historial detallado de todas las comandas cobradas o pérdidas,
    filtrado según los parámetros globales y de búsqueda.
    """
    base_pagos, _ = _get_base_pagos(request)
    
    search = request.GET.get('search', '').strip()
    if search:
        import re
        # Búsqueda flexible e inteligente
        # 1. Detectar si busca una mesa con prefijo (ej: "mesa 1", "Mesa 3", "m 2")
        match = re.search(r'(?:mesa|m)\s*(\d+)', search, re.IGNORECASE)
        
        # 2. Verificar si la búsqueda es puramente numérica
        is_numeric = search.isdigit()
        
        query = Q()
        if match:
            # Búsqueda exacta de mesa si especifica "mesa X"
            numero_mesa = int(match.group(1))
            query |= Q(comanda__mesa__numero=numero_mesa)
        elif is_numeric:
            # Si escribe solo un número (ej. "1"):
            # - Si tiene menos de 3 dígitos (ej. "1", "10"), buscamos por mesa exacta.
            # - Si tiene 3 o más dígitos (ej. "101"), puede ser un código de comanda o mesa grande.
            numero_mesa = int(search)
            query |= Q(comanda__mesa__numero=numero_mesa)
            if len(search) >= 3:
                query |= Q(comanda__codigo_comanda__icontains=search)
        else:
            # Búsqueda general de texto en otros campos
            query |= Q(comanda__codigo_comanda__icontains=search)
            query |= Q(comanda__mozo__username__icontains=search)
            query |= Q(comanda__mozo__nombres__icontains=search)
            query |= Q(comanda__mozo__apellidos__icontains=search)
            query |= Q(comanda__nombre_cliente__icontains=search)
            
        base_pagos = base_pagos.filter(query)

    comandas_ids = base_pagos.values_list('comanda_id', flat=True).distinct()
    
    comandas_qs = Comanda.objects.filter(
        id__in=comandas_ids
    ).distinct().select_related('mesa', 'mozo').prefetch_related(
        'lineas__plato', 'pagos__metodo_pago', 'pagos__caja_turno__cajero'
    ).order_by('-fecha_cierre')

    TAX_RATE = 0.10  # IGV 10%
    results = []
    
    for c in comandas_qs:
        lineas_activas = c.lineas.exclude(estado=LineaComanda.Estado.ANULADO)
        detalle = ', '.join(
            f"{l.cantidad}x {l.plato.nombre}" for l in lineas_activas
        )

        pago = c.pagos.filter(id__in=base_pagos.values_list('id', flat=True)).order_by('-fecha_pago').first()
        if not pago:
            pago = c.pagos.order_by('-fecha_pago').first()
            
        bruto = float(c.total)
        impuesto = round(bruto * TAX_RATE, 2)
        neto = round(bruto - impuesto, 2)
        es_multi = c.pagos.count() > 1

        turno_nombre = '—'
        if pago and pago.caja_turno and pago.caja_turno.cajero:
            turno_nombre = pago.caja_turno.cajero.get_turno_display().replace('Turno ', '')

        results.append({
            'id': c.id,
            'codigo': c.codigo_comanda,
            'fecha': timezone.localtime(pago.fecha_pago).strftime('%d/%m/%Y %H:%M') if pago and pago.fecha_pago else '—',
            'mesa': str(c.mesa.numero),
            'mozo': f"{c.mozo.nombres} {c.mozo.apellidos}".strip() or c.mozo.username,
            'detalle': detalle or '—',
            'bruto': bruto,       # Ganancia Final
            'impuesto': impuesto,
            'neto': neto,         # Precio Inicial
            'metodo': pago.metodo_pago.nombre if (pago and pago.metodo_pago) else 'N/A',
            'estado': pago.estado if pago else c.estado,
            'es_multi': es_multi,
            'turno': turno_nombre,
        })

    return Response({'results': results})


@api_view(['GET'])
@permission_classes([EsCajeroOAdmin])
def api_exportar_csv(request):
    """
    Genera y descarga un archivo CSV profesional con BOM UTF-8
    para que Excel lo abra correctamente con tildes y caracteres especiales.
    """
    turno = CajaTurno.objects.filter(estado=CajaTurno.Estado.ABIERTA).first()
    if not turno:
        return Response({'error': 'No hay turno activo'}, status=400)

    response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
    response['Content-Disposition'] = f'attachment; filename="Reporte_Ventas_{turno.codigo_turno}.csv"'

    # utf-8-sig agrega el BOM automáticamente — Excel lo detecta y muestra tildes correctamente
    writer = csv.writer(response, delimiter=',', quotechar='"', quoting=csv.QUOTE_ALL)

    # ── Encabezado del reporte ──
    writer.writerow(['REPORTE DE VENTAS', '', '', '', '', '', '', '', ''])
    writer.writerow(['Turno:', turno.codigo_turno, '', 'Cajero:', turno.cajero.username, '', 'Fecha apertura:', turno.fecha_apertura.strftime('%d/%m/%Y %H:%M'), ''])
    writer.writerow(['Estado:', turno.get_estado_display(), '', 'Punto de caja:', turno.get_punto_caja_display(), '', '', '', ''])
    writer.writerow(['', '', '', '', '', '', '', '', ''])  # fila vacía

    # ── Cabecera de columnas ──
    writer.writerow([
        'N°',
        'Código Comanda',
        'Mesa',
        'Mozo',
        'Apertura',
        'Cierre',
        'Detalle',
        'Método de Pago',
        'Estado',
        'Precio Neto (sin IGV)',
        'IGV (18%)',
        'Total Bruto',
    ])

    TAX_RATE = 0.18
    comandas = Comanda.objects.filter(
        pagos__caja_turno=turno
    ).distinct().select_related('mesa', 'mozo').prefetch_related(
        'lineas__plato', 'pagos__metodo_pago'
    ).order_by('fecha_apertura')

    total_bruto = 0
    total_igv = 0
    total_neto = 0
    total_perdidas = 0
    contador = 1

    for c in comandas:
        pago = c.pagos.filter(caja_turno=turno).first()
        bruto = float(c.total)
        impuesto = round(bruto * TAX_RATE, 2)
        neto = round(bruto - impuesto, 2)
        
        if pago and pago.estado == Pago.Estado.PERDIDA:
            metodo_display = 'PÉRDIDA'
        elif pago:
            metodo_display = pago.metodo_pago.nombre
        else:
            metodo_display = 'N/A'

        writer.writerow([
            c.codigo_comanda,
            c.mesa.numero,
            c.mozo.username,
            c.fecha_apertura.strftime('%Y-%m-%d %H:%M'),
            c.fecha_cierre.strftime('%Y-%m-%d %H:%M') if c.fecha_cierre else '',
            bruto,
            impuesto,
            neto,
            metodo_display
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
