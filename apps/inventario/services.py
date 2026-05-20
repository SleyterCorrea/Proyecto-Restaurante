"""Lógica de inventario compartida (descuentos por preparación, etc.)."""
import io
import logging
from decimal import Decimal

from django.db import transaction
from django.db.models import F

from apps.comandas.models import LineaComanda
from apps.inventario.models import Insumo, MovimientoInventario, RecetaInsumo

logger = logging.getLogger(__name__)


def descontar_inventario_al_marcar_listo(linea: LineaComanda, usuario):
    """
    Descuenta insumos según receta cuando una línea pasa a LISTO (cocina terminó).
    Optimizado con bulk_create y bulk_update para evitar N+1.
    """
    if linea.estado != LineaComanda.Estado.LISTO:
        return

    recetas = list(RecetaInsumo.objects.filter(plato=linea.plato, activo=True).select_related('insumo'))
    if not recetas:
        return

    insumo_ids = [r.insumo_id for r in recetas]
    insumos_a_actualizar = {i.id: i for i in Insumo.objects.select_for_update().filter(pk__in=insumo_ids)}
    movimientos_a_crear = []

    for receta in recetas:
        insumo = insumos_a_actualizar.get(receta.insumo_id)
        if not insumo:
            continue

        cantidad = Decimal(str(receta.cantidad_por_porcion * linea.cantidad))
        stock_anterior = insumo.stock_real

        nuevo_stock = insumo.stock_real - cantidad
        if nuevo_stock < 0:
            nuevo_stock = Decimal('0')

        insumo.stock_real = nuevo_stock

        movimientos_a_crear.append(MovimientoInventario(
            insumo=insumo,
            tipo_movimiento=MovimientoInventario.TipoMovimiento.CONSUMO,
            cantidad=cantidad,
            stock_anterior=stock_anterior,
            stock_nuevo=nuevo_stock,
            usuario=usuario,
            referencia_tipo='LINEA_COMANDA',
            referencia_id=linea.id,
            observacion=f'Consumo por preparación (línea {linea.id}, {linea.plato.nombre})',
        ))

    Insumo.objects.bulk_update(insumos_a_actualizar.values(), ['stock_real'])
    MovimientoInventario.objects.bulk_create(movimientos_a_crear)


def obtener_insumos_criticos():
    """
    Retorna todos los insumos con stock real <= stock mínimo (críticos).
    Incluye información de platos afectados (aquellos que usan ese insumo).
    """
    # Importación diferida para evitar circular imports
    from apps.menu.models import Plato

    criticos = Insumo.objects.filter(
        stock_real__lte=F('stock_minimo'),  # stock_real <= stock_minimo
        activo=True
    ).select_related('unidad_medida')

    resultado = []
    for insumo in criticos:
        # insumo.platos → RecetaInsumo objects (related_name='platos' en RecetaInsumo.insumo)
        # Necesitamos los Plato reales a través del FK receta.plato
        platos_qs = Plato.objects.filter(
            receta__insumo=insumo,
            receta__activo=True,
            activo=True
        ).values('id', 'nombre', 'disponible').distinct()

        platos_afectados = list(platos_qs)
        estado = 'agotado' if insumo.stock_real <= 0 else 'bajo'

        resultado.append({
            'id':              insumo.id,
            'nombre':          insumo.nombre,
            'stock_real':      float(insumo.stock_real),
            'stock_minimo':    float(insumo.stock_minimo),
            'unidad':          insumo.unidad_medida.abreviatura,
            'estado':          estado,
            'platos_afectados': platos_afectados,
            'falta':           float(max(insumo.stock_minimo - insumo.stock_real, 0)),
        })

    return resultado


def verificar_disponibilidad_plato(plato):
    """
    Verifica si un plato tiene suficientes insumos en stock.
    Retorna (disponible: bool, motivo: str)
    """
    if not plato.activo:
        return False, "Plato desactivado"

    recetas = RecetaInsumo.objects.filter(plato=plato, activo=True).select_related('insumo')

    for receta in recetas:
        insumo = receta.insumo
        if insumo.stock_real <= 0:
            return False, f"Sin stock: {insumo.nombre}"
        if insumo.stock_real <= insumo.stock_minimo:
            return False, f"Stock crítico: {insumo.nombre}"

    return True, "Disponible"


def actualizar_disponibilidad_platos(insumo):
    """
    Sincroniza la disponibilidad de todos los platos que usan este insumo.
    Se activa automáticamente cuando cambia el stock de un insumo.
    """
    from apps.menu.models import Plato

    with transaction.atomic():
        # PostgreSQL no soporta FOR UPDATE con DISTINCT: separar en dos queries
        platos_ids = list(Plato.objects.filter(
            receta__insumo=insumo,
            receta__activo=True,
            activo=True,
        ).distinct().values_list('id', flat=True))

        platos_afectados = Plato.objects.select_for_update().filter(pk__in=platos_ids)

        for plato in platos_afectados:
            disponible, _motivo = verificar_disponibilidad_plato(plato)
            if plato.disponible != disponible:
                plato.disponible = disponible
                plato.save(update_fields=['disponible'])


def obtener_stock_bajo():
    """
    Retorna insumos con stock bajo (entre 0 y stock_minimo exclusive).
    """
    bajo = Insumo.objects.filter(
        stock_real__gt=0,
        stock_real__lt=F('stock_minimo'),
        activo=True
    ).select_related('unidad_medida')

    resultado = []
    for insumo in bajo:
        if insumo.stock_minimo and insumo.stock_minimo > 0:
            porcentaje_dec = (insumo.stock_real / insumo.stock_minimo) * Decimal('100')
            porcentaje = float(porcentaje_dec.quantize(Decimal('0.01')))
        else:
            porcentaje = 0.0
        resultado.append({
            'id':           insumo.id,
            'nombre':       insumo.nombre,
            'stock_real':   float(insumo.stock_real),
            'stock_minimo': float(insumo.stock_minimo),
            'unidad':       insumo.unidad_medida.abreviatura,
            'porcentaje':   porcentaje,
        })

    return resultado


# ─── Reporte PDF de inventario ──────────────────────────────────────────────
def generar_reporte_pdf(usuario):
    """Genera un PDF con el inventario actual (Obsidian Metric look)."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from django.utils import timezone

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                            rightMargin=15*mm, leftMargin=15*mm,
                            topMargin=15*mm, bottomMargin=15*mm)
    styles = getSampleStyleSheet()
    titulo_style = ParagraphStyle('Titulo', parent=styles['Title'], fontSize=18,
                                   textColor=colors.HexColor('#6d3bd7'),
                                   spaceAfter=6, fontName='Helvetica-Bold')
    subtitulo_style = ParagraphStyle('Sub', parent=styles['Normal'], fontSize=9,
                                      textColor=colors.HexColor('#6b7280'), spaceAfter=12)

    story = []
    story.append(Paragraph('Reporte de Inventario', titulo_style))
    ts = timezone.localtime(timezone.now()).strftime('%d/%m/%Y %H:%M')
    story.append(Paragraph(
        f'Generado el {ts} por <b>{usuario.username}</b>', subtitulo_style
    ))

    # KPIs resumen
    insumos = list(Insumo.objects.filter(activo=True).select_related('unidad_medida').order_by('categoria', 'nombre'))
    total = len(insumos)
    bajos = sum(1 for i in insumos if 0 < i.stock_real <= i.stock_minimo)
    agotados = sum(1 for i in insumos if i.stock_real <= 0)
    valor_total = sum(i.stock_real * i.costo_unitario for i in insumos)

    kpi_data = [
        ['Total insumos', 'Bajo stock', 'Sin stock', 'Valor en stock'],
        [str(total), str(bajos), str(agotados), f'S/. {valor_total:,.2f}'],
    ]
    kpi_table = Table(kpi_data, colWidths=[42*mm]*4)
    kpi_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f3f4f6')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#374151')),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 8),
        ('FONTSIZE', (0, 1), (-1, 1), 14),
        ('FONTNAME', (0, 1), (-1, 1), 'Helvetica-Bold'),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('TEXTCOLOR', (1, 1), (1, 1), colors.HexColor('#b45309')),
        ('TEXTCOLOR', (2, 1), (2, 1), colors.HexColor('#dc2626')),
        ('TEXTCOLOR', (3, 1), (3, 1), colors.HexColor('#6d3bd7')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e5e7eb')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(kpi_table)
    story.append(Spacer(1, 12))

    # Tabla principal
    data = [['Categoría', 'Insumo', 'Unidad', 'Stock real', 'Mínimo', 'Costo S/.', 'Valor S/.', 'Estado']]
    for i in insumos:
        estado = 'AGOTADO' if i.stock_real <= 0 else ('BAJO' if i.stock_real <= i.stock_minimo else 'OK')
        valor = i.stock_real * i.costo_unitario
        data.append([
            i.get_categoria_display(),
            i.nombre,
            i.unidad_medida.abreviatura,
            f'{i.stock_real:.2f}',
            f'{i.stock_minimo:.2f}',
            f'{i.costo_unitario:.2f}',
            f'{valor:.2f}',
            estado,
        ])

    tabla = Table(data, colWidths=[26*mm, 42*mm, 14*mm, 20*mm, 18*mm, 18*mm, 20*mm, 20*mm])
    estilo = [
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1f2937')),
        ('TEXTCOLOR',  (0, 0), (-1, 0), colors.white),
        ('FONTNAME',   (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE',   (0, 0), (-1, 0), 8),
        ('FONTSIZE',   (0, 1), (-1, -1), 8),
        ('ALIGN',      (3, 1), (6, -1), 'RIGHT'),
        ('ALIGN',      (2, 1), (2, -1), 'CENTER'),
        ('ALIGN',      (7, 1), (7, -1), 'CENTER'),
        ('GRID',       (0, 0), (-1, -1), 0.3, colors.HexColor('#e5e7eb')),
        ('VALIGN',     (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]
    # Colorear filas por estado
    for idx, row in enumerate(data[1:], start=1):
        if row[7] == 'AGOTADO':
            estilo.append(('BACKGROUND', (0, idx), (-1, idx), colors.HexColor('#fef2f2')))
            estilo.append(('TEXTCOLOR', (7, idx), (7, idx), colors.HexColor('#dc2626')))
        elif row[7] == 'BAJO':
            estilo.append(('BACKGROUND', (0, idx), (-1, idx), colors.HexColor('#fffbeb')))
            estilo.append(('TEXTCOLOR', (7, idx), (7, idx), colors.HexColor('#b45309')))
        else:
            estilo.append(('TEXTCOLOR', (7, idx), (7, idx), colors.HexColor('#059669')))

    tabla.setStyle(TableStyle(estilo))
    story.append(tabla)

    story.append(Spacer(1, 14))
    pie = ParagraphStyle('Pie', parent=styles['Normal'], fontSize=7,
                         textColor=colors.HexColor('#9ca3af'), alignment=1)
    story.append(Paragraph(
        f'RestaurantOS · Reporte de inventario · {ts}', pie))

    doc.build(story)
    buffer.seek(0)
    return buffer


def notificar_stock_critico_si_aplica(insumo):
    """
    Envía email a los administradores cuando un insumo cruza la línea a BAJO o AGOTADO.
    Solo se llama cuando el stock_real cambió a la baja. Idempotente: no repite si ya está bajo.
    """
    from django.conf import settings
    from django.core.mail import send_mail
    from django.contrib.auth import get_user_model

    User = get_user_model()
    if insumo.stock_real > insumo.stock_minimo:
        return  # nada que alertar

    nivel = 'AGOTADO' if insumo.stock_real <= 0 else 'BAJO'
    asunto = f'⚠ [Inventario] {insumo.nombre} en estado {nivel}'
    cuerpo = (
        f'El insumo "{insumo.nombre}" ha cruzado el umbral crítico.\n\n'
        f'  • Stock actual: {insumo.stock_real} {insumo.unidad_medida.abreviatura}\n'
        f'  • Stock mínimo: {insumo.stock_minimo} {insumo.unidad_medida.abreviatura}\n'
        f'  • Estado: {nivel}\n\n'
        f'Genera una orden de compra desde el panel de inventario para reponer.\n'
    )

    # Buscar admins activos con email
    try:
        admins_emails = list(User.objects.filter(
            is_active=True,
            rol__nombre__in=['ADMIN'],
        ).exclude(email='').values_list('email', flat=True))
    except Exception:
        admins_emails = []

    if not admins_emails:
        logger.info('Sin admins con email configurado; alerta de stock se loggea solamente: %s [%s]', insumo.nombre, nivel)
        return

    try:
        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@restaurantos.local')
        send_mail(asunto, cuerpo, from_email, admins_emails, fail_silently=True)
        logger.warning('Alerta de stock %s enviada a %d admin(s) para insumo %s', nivel, len(admins_emails), insumo.nombre)
    except Exception:
        logger.exception('Error enviando alerta de stock para insumo %s', insumo.nombre)
