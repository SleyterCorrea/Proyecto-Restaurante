"""Lógica de inventario compartida (descuentos por preparación, etc.)."""
import io
import logging
from collections import defaultdict
from datetime import timedelta
from decimal import Decimal

from django.core.cache import cache
from django.db import models, transaction
from django.utils import timezone

from apps.auditoria.constants import obtener_umbral
from apps.auditoria.models import AuditLog
from apps.auditoria.services import AuditoriaService
from apps.comandas.models import LineaComanda
from apps.core.exceptions import DatosInvalidos, OperacionNoPermitida, RecursoNoEncontrado, StockInsuficiente
from apps.inventario.models import (
    Insumo,
    MovimientoInventario,
    OrdenCompra,
    OrdenCompraItem,
    RecetaInsumo,
)

logger = logging.getLogger(__name__)


class InventarioService:
    """Coordinates stock validation and inventory movements."""

    @staticmethod
    def _contextualizar_cambio(insumo, usuario=None, request=None):
        insumo._auditoria_usuario = usuario
        insumo._auditoria_request = request

    @staticmethod
    def _registrar_alerta(
        *, accion, insumo, usuario, descripcion, valores_nuevos,
        severidad=AuditLog.Severidad.ADVERTENCIA, request=None,
        impacto=None, clave_alerta=None,
    ):
        return AuditoriaService.registrar(
            usuario=usuario,
            accion=accion,
            modulo='INVENTARIO',
            entidad='INSUMO',
            entidad_id=insumo.id,
            severidad=severidad,
            estado_resultado=AuditLog.EstadoResultado.EXITOSO,
            descripcion=descripcion,
            valores_nuevos=valores_nuevos,
            request=request,
            datos_contextuales={
                'impacto_economico_estimado': impacto,
            } if impacto is not None else None,
            deduplicar_alerta=True,
            clave_alerta=clave_alerta,
        )

    @staticmethod
    def evaluar_alertas_stock(insumo, usuario=None, request=None, ahora=None):
        """Evalua agotamiento y bajo stock persistentes, y resuelve recuperaciones."""
        ahora = ahora or timezone.now()
        campos = []

        if insumo.stock_real <= 0:
            if insumo.agotado_desde is None:
                insumo.agotado_desde = ahora
                campos.append('agotado_desde')
            if insumo.stock_bajo_desde is not None:
                insumo.stock_bajo_desde = None
                campos.append('stock_bajo_desde')
            AuditoriaService.resolver_alerta(
                accion='INVENTARIO_STOCK_BAJO_PERSISTENTE',
                entidad='INSUMO',
                entidad_id=insumo.id,
            )
            limite_horas = obtener_umbral(
                'INVENTARIO_AGOTADO_CRITICO_HORAS'
                if insumo.es_critico
                else 'INVENTARIO_AGOTADO_NO_CRITICO_HORAS'
            )
            if ahora - insumo.agotado_desde >= timedelta(hours=limite_horas):
                InventarioService._registrar_alerta(
                    accion='INVENTARIO_INSUMO_AGOTADO_SIN_REPOSICION',
                    insumo=insumo,
                    usuario=usuario,
                    descripcion=f'{insumo.nombre} permanece agotado sin reposicion.',
                    valores_nuevos={
                        'stock_real': str(insumo.stock_real),
                        'agotado_desde': insumo.agotado_desde.isoformat(),
                        'limite_horas': limite_horas,
                        'es_critico': insumo.es_critico,
                    },
                    severidad=AuditLog.Severidad.CRITICA,
                    request=request,
                )
        elif insumo.stock_real <= insumo.stock_minimo:
            if insumo.stock_bajo_desde is None:
                insumo.stock_bajo_desde = ahora
                campos.append('stock_bajo_desde')
            if insumo.agotado_desde is not None:
                insumo.agotado_desde = None
                campos.append('agotado_desde')
            AuditoriaService.resolver_alerta(
                accion='INVENTARIO_INSUMO_AGOTADO_SIN_REPOSICION',
                entidad='INSUMO',
                entidad_id=insumo.id,
            )
            limite_dias = obtener_umbral('INVENTARIO_STOCK_BAJO_DIAS')
            if ahora - insumo.stock_bajo_desde >= timedelta(days=limite_dias):
                InventarioService._registrar_alerta(
                    accion='INVENTARIO_STOCK_BAJO_PERSISTENTE',
                    insumo=insumo,
                    usuario=usuario,
                    descripcion=f'{insumo.nombre} mantiene stock bajo de forma persistente.',
                    valores_nuevos={
                        'stock_real': str(insumo.stock_real),
                        'stock_minimo': str(insumo.stock_minimo),
                        'stock_bajo_desde': insumo.stock_bajo_desde.isoformat(),
                        'limite_dias': limite_dias,
                    },
                    request=request,
                )
        else:
            if insumo.agotado_desde is not None:
                insumo.agotado_desde = None
                campos.append('agotado_desde')
            if insumo.stock_bajo_desde is not None:
                insumo.stock_bajo_desde = None
                campos.append('stock_bajo_desde')
            for accion in (
                'INVENTARIO_INSUMO_AGOTADO_SIN_REPOSICION',
                'INVENTARIO_STOCK_BAJO_PERSISTENTE',
                'INVENTARIO_STOCK_INSUFICIENTE_REITERADO',
            ):
                AuditoriaService.resolver_alerta(
                    accion=accion,
                    entidad='INSUMO',
                    entidad_id=insumo.id,
                )

        if campos:
            Insumo.objects.filter(pk=insumo.pk).update(**{
                campo: getattr(insumo, campo) for campo in campos
            })
        return insumo

    @staticmethod
    def evaluar_alertas_persistentes(usuario=None, request=None, ahora=None):
        for insumo in Insumo.objects.filter(activo=True):
            InventarioService.evaluar_alertas_stock(
                insumo, usuario=usuario, request=request, ahora=ahora
            )

    @staticmethod
    def registrar_bloqueo_stock(insumo, usuario, requerido, request=None):
        """Cuenta bloqueos por turno y audita solo al alcanzar el limite."""
        from apps.caja.models import CajaTurno

        turno = CajaTurno.objects.filter(
            estado=CajaTurno.Estado.ABIERTA
        ).only('id').first()
        turno_clave = turno.id if turno else timezone.localdate().isoformat()
        limite = obtener_umbral('INVENTARIO_BLOQUEOS_STOCK_TURNO')
        cache_key = f'audit:stock-bloqueado:{turno_clave}:{insumo.id}'
        cache.add(cache_key, 0, timeout=24 * 60 * 60)
        intentos = cache.incr(cache_key)
        if intentos < limite:
            return None
        return InventarioService._registrar_alerta(
            accion='INVENTARIO_STOCK_INSUFICIENTE_REITERADO',
            insumo=insumo,
            usuario=usuario,
            descripcion=f'{insumo.nombre} bloqueo pedidos reiteradamente por falta de stock.',
            valores_nuevos={
                'intentos': intentos,
                'limite': limite,
                'turno_caja_id': getattr(turno, 'id', None),
                'stock_real': str(insumo.stock_real),
                'requerido': str(requerido),
            },
            severidad=AuditLog.Severidad.CRITICA,
            request=request,
            clave_alerta=(
                f'INVENTARIO_STOCK_INSUFICIENTE_REITERADO:'
                f'{insumo.id}:{turno_clave}'
            ),
        )

    @staticmethod
    def registrar_excepcion_stock(exc, usuario, request=None):
        insumo_id = getattr(exc, 'insumo_id', None)
        if not insumo_id:
            return None
        try:
            insumo = Insumo.objects.get(pk=insumo_id)
        except Insumo.DoesNotExist:
            return None
        return InventarioService.registrar_bloqueo_stock(
            insumo,
            usuario,
            getattr(exc, 'requerido', None),
            request=request,
        )

    @staticmethod
    def verificar_stock_plato(plato, cantidad=1):
        recetas = RecetaInsumo.objects.filter(
            plato=plato, activo=True
        ).select_related("insumo")
        for receta in recetas:
            requerido = receta.cantidad_por_porcion * Decimal(str(cantidad))
            if not receta.insumo.activo or receta.insumo.stock_real < requerido:
                raise StockInsuficiente(
                    receta.insumo.nombre,
                    receta.insumo.stock_real,
                    requerido,
                    insumo_id=receta.insumo.id,
                )
        return True

    @staticmethod
    @transaction.atomic
    def descontar_lineas(lineas, usuario, request=None):
        """Deducts recipe stock once per order line and records every movement."""
        lineas = list(lineas)
        if not lineas:
            return 0

        descontadas = set(
            MovimientoInventario.objects.filter(
                referencia_tipo="LINEA_COMANDA",
                referencia_id__in=[linea.id for linea in lineas],
                tipo_movimiento=MovimientoInventario.TipoMovimiento.CONSUMO,
            ).values_list("referencia_id", flat=True)
        )
        pendientes = [linea for linea in lineas if linea.id not in descontadas]
        if not pendientes:
            return 0

        recetas = list(
            RecetaInsumo.objects.filter(
                plato_id__in={linea.plato_id for linea in pendientes}, activo=True
            ).select_related("insumo")
        )
        recetas_por_plato = defaultdict(list)
        for receta in recetas:
            recetas_por_plato[receta.plato_id].append(receta)

        insumo_ids = sorted({receta.insumo_id for receta in recetas})
        insumos = {
            insumo.id: insumo
            for insumo in Insumo.objects.select_for_update().filter(pk__in=insumo_ids)
        }
        requerimientos = defaultdict(Decimal)
        for linea in pendientes:
            for receta in recetas_por_plato[linea.plato_id]:
                requerimientos[receta.insumo_id] += (
                    receta.cantidad_por_porcion * Decimal(str(linea.cantidad))
                )
        for insumo_id, requerido in requerimientos.items():
            insumo = insumos[insumo_id]
            if not insumo.activo or insumo.stock_real < requerido:
                raise StockInsuficiente(
                    insumo.nombre, insumo.stock_real, requerido, insumo_id=insumo.id
                )

        movimientos = []
        for linea in pendientes:
            for receta in recetas_por_plato[linea.plato_id]:
                insumo = insumos[receta.insumo_id]
                cantidad = receta.cantidad_por_porcion * Decimal(str(linea.cantidad))
                anterior = insumo.stock_real
                insumo.stock_real -= cantidad
                movimientos.append(MovimientoInventario(
                    insumo=insumo,
                    tipo_movimiento=MovimientoInventario.TipoMovimiento.CONSUMO,
                    cantidad=cantidad,
                    stock_anterior=anterior,
                    stock_nuevo=insumo.stock_real,
                    usuario=usuario,
                    referencia_tipo="LINEA_COMANDA",
                    referencia_id=linea.id,
                    observacion=f"Consumo por cobro de linea {linea.id} ({linea.plato.nombre})",
                ))

        Insumo.objects.bulk_update(insumos.values(), ["stock_real"])
        MovimientoInventario.objects.bulk_create(movimientos)
        for insumo in insumos.values():
            actualizar_disponibilidad_platos(insumo, usuario=usuario, request=request)
            InventarioService.evaluar_alertas_stock(
                insumo, usuario=usuario, request=request
            )
        return len(pendientes)

    @staticmethod
    @transaction.atomic
    def reponer(
        insumo_id, cantidad, usuario, observacion="", lote=None,
        costo_unitario=None, request=None, referencia_tipo=None,
        referencia_id=None,
    ):
        cantidad = Decimal(str(cantidad))
        if cantidad <= 0:
            raise DatosInvalidos("La cantidad debe ser mayor a cero.")
        try:
            insumo = Insumo.objects.select_for_update().get(pk=insumo_id, activo=True)
        except Insumo.DoesNotExist:
            raise RecursoNoEncontrado("Insumo no encontrado.")
        lote = str(lote or '').strip() or None
        lote_repetido = bool(lote and MovimientoInventario.objects.filter(
            insumo=insumo,
            lote=lote,
            tipo_movimiento=MovimientoInventario.TipoMovimiento.ENTRADA,
        ).exists())
        anterior = insumo.stock_real
        costo_anterior = insumo.costo_unitario
        costo_informado = costo_unitario not in (None, '')
        costo_nuevo = (
            Decimal(str(costo_unitario))
            if costo_unitario not in (None, '')
            else costo_anterior
        )
        if costo_nuevo < 0:
            raise DatosInvalidos("El costo unitario no puede ser negativo.")
        insumo.stock_real += cantidad
        insumo.stock_actual += cantidad
        insumo.costo_unitario = costo_nuevo
        InventarioService._contextualizar_cambio(insumo, usuario, request)
        insumo.save(update_fields=["stock_real", "stock_actual", "costo_unitario"])
        movimiento = MovimientoInventario.objects.create(
            insumo=insumo,
            tipo_movimiento=MovimientoInventario.TipoMovimiento.ENTRADA,
            cantidad=cantidad,
            stock_anterior=anterior,
            stock_nuevo=insumo.stock_real,
            costo_unitario=costo_nuevo,
            lote=lote,
            referencia_tipo=referencia_tipo,
            referencia_id=referencia_id,
            usuario=usuario,
            observacion=observacion,
        )
        if lote_repetido:
            InventarioService._registrar_alerta(
                accion='INVENTARIO_LOTE_REPETIDO',
                insumo=insumo,
                usuario=usuario,
                descripcion=f'Se ingreso nuevamente el lote {lote} para {insumo.nombre}.',
                valores_nuevos={'lote': lote, 'movimiento_id': movimiento.id},
                request=request,
                clave_alerta=f'INVENTARIO_LOTE_REPETIDO:{insumo.id}:{lote}',
            )
        if costo_informado and costo_anterior > 0:
            variacion = abs(costo_nuevo - costo_anterior) / costo_anterior * Decimal('100')
            if variacion > obtener_umbral('INVENTARIO_VARIACION_COSTO_PORCENTAJE'):
                InventarioService._registrar_alerta(
                    accion='INVENTARIO_COSTO_UNITARIO_VARIACION_ALTA',
                    insumo=insumo,
                    usuario=usuario,
                    descripcion=f'El costo unitario de {insumo.nombre} tuvo una variacion alta.',
                    valores_nuevos={
                        'costo_anterior': str(costo_anterior),
                        'costo_nuevo': str(costo_nuevo),
                        'variacion_porcentaje': str(variacion),
                        'movimiento_id': movimiento.id,
                    },
                    request=request,
                )
            else:
                AuditoriaService.resolver_alerta(
                    accion='INVENTARIO_COSTO_UNITARIO_VARIACION_ALTA',
                    entidad='INSUMO', entidad_id=insumo.id,
                )
        InventarioService.evaluar_alertas_stock(insumo, usuario, request)
        return insumo

    @staticmethod
    @transaction.atomic
    def ajustar(insumo_id, cantidad, tipo, motivo, usuario, request=None):
        cantidad = Decimal(str(cantidad))
        if cantidad <= 0:
            raise DatosInvalidos("La cantidad debe ser mayor a cero.")
        if tipo not in (
            MovimientoInventario.TipoMovimiento.AJUSTE_POS,
            MovimientoInventario.TipoMovimiento.AJUSTE_NEG,
        ):
            raise DatosInvalidos("Tipo de ajuste invalido.")
        try:
            insumo = Insumo.objects.select_for_update().get(pk=insumo_id, activo=True)
        except Insumo.DoesNotExist:
            raise RecursoNoEncontrado("Insumo no encontrado.")
        anterior = insumo.stock_real
        if tipo == MovimientoInventario.TipoMovimiento.AJUSTE_POS:
            insumo.stock_real += cantidad
            insumo.stock_actual += cantidad
        else:
            if insumo.stock_real < cantidad:
                raise StockInsuficiente(
                    insumo.nombre, insumo.stock_real, cantidad, insumo_id=insumo.id
                )
            insumo.stock_real -= cantidad
            insumo.stock_actual -= cantidad
        InventarioService._contextualizar_cambio(insumo, usuario, request)
        insumo.save(update_fields=["stock_real", "stock_actual"])
        movimiento = MovimientoInventario.objects.create(
            insumo=insumo,
            tipo_movimiento=tipo,
            cantidad=cantidad,
            stock_anterior=anterior,
            stock_nuevo=insumo.stock_real,
            usuario=usuario,
            observacion=motivo,
        )
        porcentaje = (
            cantidad / anterior * Decimal('100')
            if anterior > 0 else Decimal('100')
        )
        impacto = cantidad * insumo.costo_unitario
        if (
            porcentaje > obtener_umbral('INVENTARIO_AJUSTE_PORCENTAJE')
            or impacto > obtener_umbral('INVENTARIO_AJUSTE_IMPACTO')
        ):
            AuditoriaService.registrar(
                usuario=usuario,
                accion='INVENTARIO_AJUSTE_MANUAL_ELEVADO',
                modulo='INVENTARIO',
                entidad='MOVIMIENTO_INVENTARIO',
                entidad_id=movimiento.id,
                severidad=AuditLog.Severidad.CRITICA,
                estado_resultado=AuditLog.EstadoResultado.EXITOSO,
                descripcion=f'Se realizo un ajuste manual elevado de {insumo.nombre}.',
                motivo=motivo,
                valores_anteriores={'stock_real': str(anterior)},
                valores_nuevos={
                    'stock_real': str(insumo.stock_real),
                    'cantidad': str(cantidad),
                    'porcentaje': str(porcentaje),
                    'tipo': tipo,
                },
                request=request,
                datos_contextuales={
                    'impacto_economico_estimado': impacto,
                },
            )

        ventana = timezone.now() - timedelta(
            hours=obtener_umbral('INVENTARIO_AJUSTES_REPETIDOS_HORAS')
        )
        cantidad_ajustes = MovimientoInventario.objects.filter(
            insumo=insumo,
            tipo_movimiento__in=(
                MovimientoInventario.TipoMovimiento.AJUSTE_POS,
                MovimientoInventario.TipoMovimiento.AJUSTE_NEG,
            ),
            created_at__gte=ventana,
        ).count()
        if cantidad_ajustes >= obtener_umbral('INVENTARIO_AJUSTES_REPETIDOS_CANTIDAD'):
            InventarioService._registrar_alerta(
                accion='INVENTARIO_AJUSTES_REPETIDOS',
                insumo=insumo,
                usuario=usuario,
                descripcion=f'{insumo.nombre} acumula ajustes manuales reiterados.',
                valores_nuevos={
                    'cantidad_ajustes': cantidad_ajustes,
                    'ventana_horas': obtener_umbral(
                        'INVENTARIO_AJUSTES_REPETIDOS_HORAS'
                    ),
                },
                request=request,
            )
        else:
            AuditoriaService.resolver_alerta(
                accion='INVENTARIO_AJUSTES_REPETIDOS',
                entidad='INSUMO', entidad_id=insumo.id,
            )
        InventarioService.evaluar_alertas_stock(insumo, usuario, request)
        return insumo

    @staticmethod
    @transaction.atomic
    def registrar_merma(
        insumo_id, cantidad, causa, usuario, observacion="", request=None
    ):
        cantidad = Decimal(str(cantidad))
        if cantidad <= 0:
            raise DatosInvalidos("La cantidad debe ser mayor a cero.")
        try:
            insumo = Insumo.objects.select_for_update().get(pk=insumo_id, activo=True)
        except Insumo.DoesNotExist:
            raise RecursoNoEncontrado("Insumo no encontrado.")
        if insumo.stock_real < cantidad:
            raise StockInsuficiente(
                insumo.nombre, insumo.stock_real, cantidad, insumo_id=insumo.id
            )
        anterior = insumo.stock_real
        insumo.stock_real -= cantidad
        insumo.stock_actual -= cantidad
        InventarioService._contextualizar_cambio(insumo, usuario, request)
        insumo.save(update_fields=["stock_real", "stock_actual"])
        movimiento = MovimientoInventario.objects.create(
            insumo=insumo,
            tipo_movimiento=MovimientoInventario.TipoMovimiento.MERMA,
            cantidad=cantidad,
            stock_anterior=anterior,
            stock_nuevo=insumo.stock_real,
            causa_merma=causa,
            usuario=usuario,
            observacion=observacion,
        )
        hoy = timezone.localdate()
        movimientos_hoy = MovimientoInventario.objects.filter(
            insumo=insumo,
            created_at__date=hoy,
        ).order_by('created_at', 'id')
        primero = movimientos_hoy.first()
        stock_inicial = primero.stock_anterior if primero else anterior
        total_merma = movimientos_hoy.filter(
            tipo_movimiento=MovimientoInventario.TipoMovimiento.MERMA
        ).aggregate(total=models.Sum('cantidad'))['total'] or Decimal('0')
        porcentaje = (
            total_merma / stock_inicial * Decimal('100')
            if stock_inicial > 0 else Decimal('100')
        )
        if porcentaje > obtener_umbral('INVENTARIO_MERMA_PORCENTAJE'):
            InventarioService._registrar_alerta(
                accion='INVENTARIO_MERMA_ELEVADA',
                insumo=insumo,
                usuario=usuario,
                descripcion=f'La merma diaria de {insumo.nombre} supero el limite.',
                valores_nuevos={
                    'movimiento_id': movimiento.id,
                    'stock_inicial_dia': str(stock_inicial),
                    'merma_acumulada': str(total_merma),
                    'porcentaje': str(porcentaje),
                    'fecha': hoy.isoformat(),
                },
                severidad=AuditLog.Severidad.CRITICA,
                request=request,
                impacto=total_merma * insumo.costo_unitario,
                clave_alerta=f'INVENTARIO_MERMA_ELEVADA:{insumo.id}:{hoy}',
            )
        InventarioService.evaluar_alertas_stock(insumo, usuario, request)
        return insumo

    @staticmethod
    @transaction.atomic
    def registrar_egreso(
        insumo_id, cantidad, consumo_teorico, usuario, observacion='', request=None
    ):
        cantidad = Decimal(str(cantidad))
        consumo_teorico = Decimal(str(consumo_teorico))
        if cantidad <= 0 or consumo_teorico < 0:
            raise DatosInvalidos('Las cantidades del egreso no son validas.')
        try:
            insumo = Insumo.objects.select_for_update().get(pk=insumo_id, activo=True)
        except Insumo.DoesNotExist:
            raise RecursoNoEncontrado('Insumo no encontrado.')
        if insumo.stock_real < cantidad:
            raise StockInsuficiente(
                insumo.nombre, insumo.stock_real, cantidad, insumo_id=insumo.id
            )
        anterior = insumo.stock_real
        insumo.stock_real -= cantidad
        insumo.stock_actual -= cantidad
        InventarioService._contextualizar_cambio(insumo, usuario, request)
        insumo.save(update_fields=['stock_real', 'stock_actual'])
        movimiento = MovimientoInventario.objects.create(
            insumo=insumo,
            tipo_movimiento=MovimientoInventario.TipoMovimiento.SALIDA,
            cantidad=cantidad,
            stock_anterior=anterior,
            stock_nuevo=insumo.stock_real,
            costo_unitario=insumo.costo_unitario,
            usuario=usuario,
            observacion=observacion,
        )
        desviacion = (
            (cantidad - consumo_teorico) / consumo_teorico * Decimal('100')
            if consumo_teorico > 0 else Decimal('100')
        )
        if desviacion > obtener_umbral('INVENTARIO_EGRESO_DESVIACION_PORCENTAJE'):
            AuditoriaService.registrar(
                usuario=usuario,
                accion='INVENTARIO_EGRESO_INCOHERENTE',
                modulo='INVENTARIO',
                entidad='MOVIMIENTO_INVENTARIO',
                entidad_id=movimiento.id,
                severidad=AuditLog.Severidad.CRITICA,
                estado_resultado=AuditLog.EstadoResultado.EXITOSO,
                descripcion=f'El egreso de {insumo.nombre} supera el consumo teorico.',
                valores_nuevos={
                    'cantidad': str(cantidad),
                    'consumo_teorico': str(consumo_teorico),
                    'desviacion_porcentaje': str(desviacion),
                },
                request=request,
                datos_contextuales={
                    'impacto_economico_estimado': (
                        cantidad - consumo_teorico
                    ) * insumo.costo_unitario,
                },
            )
        InventarioService.evaluar_alertas_stock(insumo, usuario, request)
        return insumo

    @staticmethod
    @transaction.atomic
    def cambiar_activo(insumo_id, activo):
        try:
            insumo = Insumo.objects.select_for_update().get(pk=insumo_id)
        except Insumo.DoesNotExist:
            raise RecursoNoEncontrado("Insumo no encontrado.")
        if insumo.activo == activo:
            raise OperacionNoPermitida("El insumo ya tiene el estado solicitado.")
        insumo.activo = activo
        insumo.save(update_fields=["activo"])
        if not activo:
            RecetaInsumo.objects.filter(insumo=insumo, activo=True).update(activo=False)
            actualizar_disponibilidad_platos(insumo)
        return insumo

    @staticmethod
    @transaction.atomic
    def crear_orden(data, usuario):
        items = data.get("items", [])
        if not items:
            raise DatosInvalidos("La orden debe tener al menos un item.")
        orden = OrdenCompra.objects.create(
            codigo="TEMP",
            proveedor=data.get("proveedor", ""),
            notas=data.get("notas", ""),
            creado_por=usuario,
            estado=OrdenCompra.Estado.BORRADOR,
        )
        orden.codigo = f"OC-{timezone.localtime():%Y%m%d}-{orden.pk:04d}"
        total = Decimal("0")
        for item in items:
            try:
                insumo = Insumo.objects.get(pk=item["insumo"], activo=True)
                cantidad = Decimal(str(item.get("cantidad_solicitada", 0)))
                costo = Decimal(str(item.get("costo_unitario", insumo.costo_unitario or 0)))
            except (Insumo.DoesNotExist, KeyError, ValueError):
                raise DatosInvalidos("La orden contiene un insumo invalido.")
            if cantidad <= 0 or costo < 0:
                raise DatosInvalidos("Cantidad o costo invalido en la orden.")
            subtotal = cantidad * costo
            total += subtotal
            OrdenCompraItem.objects.create(
                orden=orden,
                insumo=insumo,
                cantidad_solicitada=cantidad,
                costo_unitario=costo,
                subtotal=subtotal,
            )
        orden.total_estimado = total
        orden.save(update_fields=["codigo", "total_estimado"])
        return orden

    @staticmethod
    @transaction.atomic
    def generar_orden_automatica(usuario, proveedor=""):
        bajos = list(Insumo.objects.filter(
            activo=True, stock_real__lte=models.F("stock_minimo")
        ))
        if not bajos:
            raise OperacionNoPermitida("No hay insumos por reponer.")
        data = {"proveedor": proveedor, "notas": "Generada automaticamente", "items": []}
        for insumo in bajos:
            objetivo = insumo.stock_minimo * 2
            data["items"].append({
                "insumo": insumo.id,
                "cantidad_solicitada": max(objetivo - insumo.stock_real, insumo.stock_minimo),
                "costo_unitario": insumo.costo_unitario,
            })
        return InventarioService.crear_orden(data, usuario)

    @staticmethod
    @transaction.atomic
    def cambiar_estado_orden(
        orden_id, nuevo_estado, usuario=None, recepciones=None, request=None
    ):
        try:
            orden = OrdenCompra.objects.select_for_update().get(pk=orden_id)
        except OrdenCompra.DoesNotExist:
            raise RecursoNoEncontrado("Orden no encontrada.")
        if nuevo_estado == OrdenCompra.Estado.ENVIADA:
            if orden.estado != OrdenCompra.Estado.BORRADOR:
                raise OperacionNoPermitida("Solo se puede enviar una orden en borrador.")
            orden.fecha_envio = timezone.now()
        elif nuevo_estado == OrdenCompra.Estado.CANCELADA:
            if orden.estado == OrdenCompra.Estado.RECIBIDA:
                raise OperacionNoPermitida("No se puede cancelar una orden recibida.")
        elif nuevo_estado == OrdenCompra.Estado.RECIBIDA:
            if orden.estado in (OrdenCompra.Estado.RECIBIDA, OrdenCompra.Estado.CANCELADA):
                raise OperacionNoPermitida("La orden no puede ser recibida.")
            recepciones = recepciones or {}
            ids = sorted(orden.items.values_list("insumo_id", flat=True))
            insumos = {i.id: i for i in Insumo.objects.select_for_update().filter(pk__in=ids)}
            for item in orden.items.select_related("insumo"):
                recepcion = recepciones.get(item.id, item.cantidad_solicitada)
                if isinstance(recepcion, dict):
                    cantidad = Decimal(str(
                        recepcion.get('cantidad', item.cantidad_solicitada)
                    ))
                    lote = recepcion.get('lote')
                    costo = recepcion.get('costo_unitario', item.costo_unitario)
                else:
                    cantidad = Decimal(str(recepcion))
                    lote = None
                    costo = item.costo_unitario
                if cantidad <= 0:
                    continue
                insumo = insumos[item.insumo_id]
                InventarioService.reponer(
                    insumo.id,
                    cantidad,
                    usuario,
                    observacion=f'Recepcion {orden.codigo}',
                    lote=lote,
                    costo_unitario=costo,
                    request=request,
                    referencia_tipo='ORDEN_COMPRA',
                    referencia_id=orden.id,
                )
                item.cantidad_recibida = cantidad
                item.save(update_fields=["cantidad_recibida"])
            orden.fecha_recepcion = timezone.now()
            orden.recibido_por = usuario
        else:
            raise DatosInvalidos("Estado de orden invalido.")
        orden.estado = nuevo_estado
        orden.save()
        return orden


def descontar_inventario_al_marcar_listo(linea: LineaComanda, usuario):
    """
    Descuenta insumos según receta cuando una línea pasa a LISTO (cocina terminó).
    Lanza ValueError si no hay stock suficiente para algún insumo.
    Usa bulk_create / bulk_update para evitar N+1, y recalcula disponibilidad
    de platos afectados porque bulk_update no dispara señales Django.
    """
    if linea.estado != LineaComanda.Estado.LISTO:
        return 0
    return InventarioService.descontar_lineas([linea], usuario)


def obtener_insumos_criticos():
    """
    Retorna todos los insumos con stock real <= stock mínimo (críticos).
    Incluye información de platos afectados (aquellos que usan ese insumo).
    """
    # Importación diferida para evitar circular imports
    InventarioService.evaluar_alertas_persistentes()
    from apps.menu.models import Plato

    criticos = Insumo.objects.criticos().select_related('unidad_medida')

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
    Verifica si un plato puede prepararse al menos una vez con el stock actual.
    Retorna (disponible: bool, motivo: str).

    Un plato se bloquea solo cuando el stock real es insuficiente para cubrir
    una porción completa — no cuando llega al mínimo de reposición.
    """
    if not plato.activo:
        return False, "Plato desactivado"

    recetas = RecetaInsumo.objects.filter(plato=plato, activo=True).select_related('insumo')
    if not recetas.exists():
        return True, "Sin receta definida"

    for receta in recetas:
        insumo = receta.insumo
        if not insumo.activo:
            return False, f"Insumo inactivo: {insumo.nombre}"
        if insumo.stock_real < receta.cantidad_por_porcion:
            return False, f"Stock insuficiente: {insumo.nombre}"

    return True, "Disponible"


def actualizar_disponibilidad_platos(insumo, usuario=None, request=None):
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
            disponible, motivo = verificar_disponibilidad_plato(plato)
            if plato.disponible != disponible:
                estado_anterior = plato.disponible
                plato.disponible = disponible
                plato.save(update_fields=['disponible'])
                if not disponible:
                    AuditoriaService.registrar(
                        usuario=usuario,
                        accion='PLATO_DESHABILITADO_STOCK',
                        modulo='MENU',
                        entidad='PLATO',
                        entidad_id=plato.id,
                        severidad=AuditLog.Severidad.ADVERTENCIA,
                        estado_resultado=AuditLog.EstadoResultado.EXITOSO,
                        descripcion=f'{plato.nombre} se deshabilito por falta de stock.',
                        valores_anteriores={'disponible': estado_anterior},
                        valores_nuevos={
                            'disponible': disponible,
                            'motivo': motivo,
                            'insumo_id': insumo.id,
                        },
                        request=request,
                        deduplicar_alerta=True,
                    )
                else:
                    AuditoriaService.resolver_alerta(
                        accion='PLATO_DESHABILITADO_STOCK',
                        entidad='PLATO',
                        entidad_id=plato.id,
                    )


def obtener_stock_bajo():
    """
    Retorna insumos con stock bajo (entre 0 y stock_minimo exclusive).
    """
    InventarioService.evaluar_alertas_persistentes()
    bajo = Insumo.objects.bajo_stock().select_related('unidad_medida')

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

    # Buscar admins activos con email (usando is_superuser)
    try:
        admins_emails = list(User.objects.filter(
            is_active=True,
            is_superuser=True
        ).exclude(email='').values_list('email', flat=True))
    except Exception:
        logger.exception('Error al consultar admins para alerta de stock del insumo %s', insumo.nombre)
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
