"""
Servicios de negocio para el módulo Caja (versión completa CAJA).

Incluye:
- procesar_cobro(): procesamiento atómico de cobros, multi-pago, cobro parcial por líneas.
- registrar_perdida(): marcar una comanda como pérdida (no pagó).
"""
import uuid
from decimal import Decimal, InvalidOperation
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError

from apps.auditoria.models import AuditLog
from apps.auditoria.services import AuditoriaService
from apps.auditoria.constants import obtener_umbral
from .models import CajaTurno, Pago, MetodoPago
from apps.core.exceptions import (
    CajaNoAbierta,
    DatosInvalidos,
    OperacionNoPermitida,
    PagoInvalido,
    RecursoNoEncontrado,
)
from apps.inventario.services import InventarioService
from apps.mesas.models import Mesa
from apps.comandas.models import Comanda, LineaComanda


def _obtener_turno_activo():
    """Devuelve el CajaTurno abierto o lanza ValidationError."""
    turno = CajaTurno.objects.filter(estado=CajaTurno.Estado.ABIERTA).first()
    if not turno:
        raise CajaNoAbierta("No hay un turno de caja abierto. Abre el turno antes de cobrar.")
    return turno


def _liberar_mesas_comanda(comanda):
    """Cambia todas las mesas de la comanda a estado LIMPIEZA y disuelve sus uniones."""
    from apps.mesas.models import UnionMesas
    from django.db.models import Q
    
    mesas = list(comanda.todas_las_mesas)
    
    # Buscar y eliminar uniones activas que incluyan a cualquiera de estas mesas
    uniones_activas = UnionMesas.objects.filter(
        Q(mesa_principal__in=mesas) | Q(mesas_secundarias__in=mesas),
        activa=True
    ).distinct()
    
    for union in uniones_activas:
        union.activa = False
        union.save(update_fields=['activa'])
        
    # Cambiar estado de todas las mesas a LIMPIEZA
    for m in mesas:
        m.estado = Mesa.Estado.LIMPIEZA
        m.save(update_fields=['estado'])


def procesar_cobro(
    comanda_id, pagos_data, usuario, linea_ids=None, observacion=None, request=None
):
    """
    Procesa el cobro de una comanda con soporte multi-pago.

    Args:
        comanda_id (int): ID de la comanda a cobrar.
        pagos_data (list): Lista de dicts con {metodo_pago_id, monto, referencia}.
                           Cada item puede ser un pago separado.
        usuario: El usuario que cobra.
        linea_ids (list[int]|None): Si se provee, solo cobra esas líneas (cobro parcial).
        observacion (str|None): Observación general del cobro.

    Returns:
        list[Pago]: Lista de pagos creados.
    """
    with transaction.atomic():
        turno = _obtener_turno_activo()

        try:
            comanda = Comanda.objects.select_for_update().get(pk=comanda_id)
        except Comanda.DoesNotExist:
            raise RecursoNoEncontrado("La comanda no existe.")

        if comanda.estado == Comanda.Estado.COBRADA:
            raise OperacionNoPermitida("Esta comanda ya fue cobrada.")

        if comanda.estado != Comanda.Estado.LISTA:
            raise OperacionNoPermitida(
                f"La comanda no está disponible para cobrar. Estado: {comanda.get_estado_display()}"
            )

        # Líneas ya pagadas en cobros previos de la comanda
        lineas_ya_pagadas_ids = set(
            LineaComanda.objects.filter(
                comanda=comanda,
                pagos__estado=Pago.Estado.PAGADO
            ).values_list('id', flat=True)
        )

        # Determinar las líneas a cobrar
        if linea_ids:
            lineas = list(
                comanda.lineas.filter(pk__in=linea_ids)
                .exclude(estado=LineaComanda.Estado.ANULADO)
                .select_related('plato')
            )
        else:
            # Si no se especifican, se cobran todas las líneas activas que aún no han sido pagadas
            lineas = list(
                comanda.lineas.exclude(estado=LineaComanda.Estado.ANULADO)
                .exclude(id__in=lineas_ya_pagadas_ids)
                .select_related('plato')
            )

        if not lineas:
            raise PagoInvalido("No hay líneas válidas para cobrar.")

        # Validar que ninguna de las líneas que se quieren pagar ahora esté ya pagada
        lineas_ahora_ids = set(l.id for l in lineas)
        lineas_repetidas = lineas_ahora_ids.intersection(lineas_ya_pagadas_ids)
        if lineas_repetidas:
            nombres_repetidos = [l.plato.nombre for l in lineas if l.id in lineas_repetidas]
            raise PagoInvalido(
                f"Las siguientes líneas ya fueron pagadas: {', '.join(nombres_repetidos)}."
            )

        # Calcular el total a cobrar según las líneas seleccionadas
        total_a_cobrar = sum(l.subtotal for l in lineas)

        # Validar que la suma de los pagos cubra el total
        total_pagado = sum(Decimal(str(p.get('monto', 0))) for p in pagos_data)
        if total_pagado < total_a_cobrar:
            raise PagoInvalido(
                f"El monto total pagado (S/. {total_pagado}) es insuficiente para cubrir S/. {total_a_cobrar}."
            )

        # Generar un ID de transacción único para agrupar todos los pagos de este cobro
        transaccion_id = str(uuid.uuid4())[:8].upper()

        if not pagos_data:
            raise PagoInvalido("Se requiere al menos un metodo de pago.")

        pagos_creados = []
        metodos_usados = []

        for i, p_data in enumerate(pagos_data):
            try:
                metodo = MetodoPago.objects.get(pk=p_data['metodo_pago_id'], activo=True)
                monto_pago = Decimal(str(p_data.get('monto', 0)))
            except (MetodoPago.DoesNotExist, KeyError, InvalidOperation):
                raise PagoInvalido("Metodo de pago o monto invalido.")
            if monto_pago <= 0:
                raise PagoInvalido("Los montos de pago deben ser mayores a cero.")
            referencia = str(p_data.get('referencia', '')).strip()
            if metodo.requiere_referencia and not referencia:
                raise PagoInvalido(f"El metodo {metodo.nombre} requiere una referencia.")
            if total_pagado > total_a_cobrar and i == len(pagos_data) - 1 and not metodo.permite_vuelto:
                raise PagoInvalido(f"El metodo {metodo.nombre} no permite un monto mayor al total.")

            # El vuelto solo aplica al último pago si hay uno solo o si el método lo permite
            if i == len(pagos_data) - 1:
                vuelto = max(Decimal('0'), total_pagado - total_a_cobrar) if metodo.permite_vuelto else Decimal('0')
            else:
                vuelto = Decimal('0')

            pago = Pago.objects.create(
                caja_turno=turno,
                comanda=comanda,
                metodo_pago=metodo,
                monto=monto_pago,
                vuelto=vuelto,
                referencia=referencia,
                transaccion_id=transaccion_id,
                estado=Pago.Estado.PAGADO,
                observacion=p_data.get('observacion') or observacion or '',
            )

            # Asociar las líneas pagadas (M2M)
            pago.lineas_pagadas.set(lineas)
            pagos_creados.append(pago)
            metodos_usados.append(metodo)

        # La deduccion forma parte de la misma transaccion del pago. El servicio
        # es idempotente para lineas descontadas por versiones anteriores.
        InventarioService.descontar_lineas(lineas, usuario, request=request)

        # Determinar si con este pago se completa toda la comanda
        lineas_activas = comanda.lineas.exclude(estado=LineaComanda.Estado.ANULADO)
        lineas_activas_ids = set(lineas_activas.values_list('id', flat=True))

        total_pagadas_ids = lineas_ya_pagadas_ids.union(lineas_ahora_ids)
        es_pago_completo = lineas_activas_ids.issubset(total_pagadas_ids)

        if es_pago_completo:
            # Si se completó el pago de toda la comanda, actualizar estado y liberar mesa
            comanda.estado = Comanda.Estado.COBRADA
            comanda.fecha_cierre = timezone.now()
            comanda.save(update_fields=['estado', 'fecha_cierre'])

            # Liberar mesas
            _liberar_mesas_comanda(comanda)

        # Actualizar totales del turno
        turno.total_ventas += total_a_cobrar
        for i, pago in enumerate(pagos_creados):
            metodo = metodos_usados[i]
            neto = pago.monto - pago.vuelto
            if metodo.codigo == 'EFECTIVO':
                turno.total_efectivo += neto
            else:
                turno.total_tarjeta += neto

        turno.save(update_fields=['total_ventas', 'total_efectivo', 'total_tarjeta'])

        return pagos_creados


def procesar_cobro_simple(comanda_id, metodo_pago_id, monto_recibido, usuario, referencia=None):
    """
    Wrapper legacy para cobros simples (un solo método de pago).
    Mantiene compatibilidad con código antiguo.
    """
    return procesar_cobro(
        comanda_id=comanda_id,
        pagos_data=[{'metodo_pago_id': metodo_pago_id, 'monto': monto_recibido, 'referencia': referencia}],
        usuario=usuario,
    )


def registrar_perdida(comanda_id, usuario, observacion, request=None):
    """
    Marca una comanda como pérdida (el cliente no pagó o se fue).

    Una pérdida representa un impacto económico real, por lo que el motivo es
    obligatorio y el evento queda trazado como crítico en Auditoría de Riesgos.
    """
    motivo = str(observacion or '').strip()
    if not motivo:
        raise DatosInvalidos("El motivo es obligatorio para registrar una pérdida.")

    with transaction.atomic():
        turno = _obtener_turno_activo()

        try:
            comanda = Comanda.objects.select_for_update().get(pk=comanda_id)
        except Comanda.DoesNotExist:
            raise RecursoNoEncontrado("La comanda no existe.")

        if comanda.estado == Comanda.Estado.COBRADA:
            raise OperacionNoPermitida("Esta comanda ya fue cobrada.")

        estado_comanda_anterior = comanda.estado

        lineas = list(
            comanda.lineas.exclude(estado=LineaComanda.Estado.ANULADO).select_related('plato')
        )
        InventarioService.descontar_lineas(lineas, usuario)

        # Usar el primer método de pago disponible (o crear uno genérico)
        metodo_perdida = MetodoPago.objects.filter(codigo='PERDIDA', activo=True).first()
        if not metodo_perdida:
            # Si no existe el método PERDIDA, usar el primer método disponible
            metodo_perdida = MetodoPago.objects.filter(activo=True).first()
            if not metodo_perdida:
                raise PagoInvalido("No hay metodos de pago disponibles.")

        pago = Pago.objects.create(
            caja_turno=turno,
            comanda=comanda,
            metodo_pago=metodo_perdida,
            monto=comanda.total,
            vuelto=Decimal('0'),
            estado=Pago.Estado.PERDIDA,
            observacion=motivo,
        )

        # Marcar como COBRADA aunque sea pérdida (para que no quede abierta)
        comanda.estado = Comanda.Estado.COBRADA
        comanda.fecha_cierre = timezone.now()
        comanda.save(update_fields=['estado', 'fecha_cierre'])

        _liberar_mesas_comanda(comanda)

        # Auditoría crítica: pérdida económica real sobre una venta.
        AuditoriaService.registrar(
            usuario=usuario,
            accion='CAJA_VENTA_PERDIDA_REGISTRADA',
            modulo='CAJA',
            entidad='PAGO',
            entidad_id=pago.id,
            severidad=AuditLog.Severidad.CRITICA,
            estado_resultado=AuditLog.EstadoResultado.EXITOSO,
            descripcion=(
                f'Venta registrada como pérdida en la comanda '
                f'{comanda.codigo_comanda} por S/ {comanda.total}.'
            ),
            motivo=motivo,
            valores_anteriores={'estado_comanda': estado_comanda_anterior},
            valores_nuevos={
                'estado_pago': Pago.Estado.PERDIDA,
                'estado_comanda': comanda.estado,
                'comanda': comanda.codigo_comanda,
                'monto': str(comanda.total),
            },
            request=request,
            datos_contextuales={'impacto_economico_estimado': comanda.total},
        )

        return pago


class CajaService:
    """Coordinates cash shifts, payments, losses, and inventory deduction."""

    @staticmethod
    @transaction.atomic
    def abrir_turno(data, usuario, request=None):
        if CajaTurno.objects.select_for_update().filter(estado=CajaTurno.Estado.ABIERTA).exists():
            raise OperacionNoPermitida("Ya existe un turno de caja abierto.")
        try:
            saldo = Decimal(str(data.get("saldo_inicial", 0)))
        except InvalidOperation:
            raise DatosInvalidos("El saldo inicial no es valido.")
        if saldo < 0:
            raise DatosInvalidos("El saldo inicial no puede ser negativo.")
        ahora = timezone.now()
        codigo = f"TUR-{ahora:%Y%m%d}-{uuid.uuid4().hex[:8].upper()}"
        turno = CajaTurno.objects.create(
            codigo_turno=codigo,
            cajero=usuario,
            saldo_inicial=saldo,
            punto_caja=data.get("punto_caja", "PLANTA_BAJA"),
            estado=CajaTurno.Estado.ABIERTA,
        )
        AuditoriaService.registrar(
            usuario=usuario,
            accion='CAJA_TURNO_ABIERTO',
            modulo='CAJA',
            entidad='CAJA_TURNO',
            entidad_id=turno.id,
            severidad=AuditLog.Severidad.INFO,
            estado_resultado=AuditLog.EstadoResultado.EXITOSO,
            descripcion=f'Se abrio el turno {turno.codigo_turno}.',
            valores_nuevos={
                'estado': turno.estado,
                'saldo_inicial': str(turno.saldo_inicial),
                'punto_caja': turno.punto_caja,
            },
            request=request,
        )
        return turno

    @staticmethod
    @transaction.atomic
    def cerrar_turno(data, usuario=None, request=None):
        try:
            turno = CajaTurno.objects.select_for_update().get(estado=CajaTurno.Estado.ABIERTA)
        except CajaTurno.DoesNotExist:
            raise CajaNoAbierta("No hay un turno abierto para cerrar.")
        except CajaTurno.MultipleObjectsReturned:
            raise OperacionNoPermitida("Existe mas de un turno abierto.")

        pendientes_cocina = LineaComanda.objects.filter(
            estado__in=[LineaComanda.Estado.PENDIENTE, LineaComanda.Estado.EN_PREP],
            comanda__estado__in=[Comanda.Estado.ABIERTA, Comanda.Estado.EN_PREPARACION, Comanda.Estado.LISTA],
        ).count()
        pendientes_servicio = LineaComanda.objects.filter(
            estado=LineaComanda.Estado.LISTO,
            comanda__estado__in=[Comanda.Estado.ABIERTA, Comanda.Estado.EN_PREPARACION, Comanda.Estado.LISTA],
        ).count()
        comandas_abiertas = Comanda.objects.filter(
            estado__in=[Comanda.Estado.ABIERTA, Comanda.Estado.EN_PREPARACION, Comanda.Estado.LISTA]
        ).count()
        forzar = data.get('forzar', False) in (True, 1, '1', 'true', 'TRUE')
        motivo = str(data.get('motivo') or data.get('observacion') or '').strip()
        if (pendientes_cocina or pendientes_servicio or comandas_abiertas) and not forzar:
            raise OperacionNoPermitida(
                "No se puede cerrar la caja mientras existan comandas o platos pendientes."
            )
        if forzar and not motivo:
            raise DatosInvalidos('El motivo es obligatorio para forzar el cierre.')
        try:
            turno.saldo_final = Decimal(str(data.get("saldo_final", 0)))
            arqueo = data.get("arqueo_fisico")
            if arqueo not in (None, ""):
                turno.arqueo_fisico = Decimal(str(arqueo))
                turno.diferencia = turno.arqueo_fisico - (turno.saldo_inicial + turno.total_efectivo)
            else:
                turno.arqueo_fisico = None
                turno.diferencia = None
        except InvalidOperation:
            raise DatosInvalidos("Los montos de cierre no son validos.")
        turno.observacion = motivo or data.get("observacion", "")
        turno.estado = CajaTurno.Estado.CERRADA
        turno.fecha_cierre = timezone.now()
        turno.save()
        usuario_auditoria = usuario or turno.cajero
        AuditoriaService.registrar(
            usuario=usuario_auditoria,
            accion='CAJA_CIERRE_FORZADO' if forzar else 'CAJA_TURNO_CERRADO',
            modulo='CAJA',
            entidad='CAJA_TURNO',
            entidad_id=turno.id,
            severidad=(
                AuditLog.Severidad.CRITICA
                if forzar else AuditLog.Severidad.INFO
            ),
            estado_resultado=AuditLog.EstadoResultado.EXITOSO,
            descripcion=(
                f'Se forzo el cierre del turno {turno.codigo_turno}.'
                if forzar else f'Se cerro el turno {turno.codigo_turno}.'
            ),
            motivo=motivo if forzar else None,
            valores_anteriores={'estado': CajaTurno.Estado.ABIERTA},
            valores_nuevos={
                'estado': turno.estado,
                'saldo_final': str(turno.saldo_final),
                'arqueo_fisico': (
                    str(turno.arqueo_fisico)
                    if turno.arqueo_fisico is not None
                    else None
                ),
                'diferencia': (
                    str(turno.diferencia)
                    if turno.diferencia is not None
                    else None
                ),
                'cierre_forzado': forzar,
                'pendientes_cocina': pendientes_cocina,
                'pendientes_servicio': pendientes_servicio,
                'comandas_abiertas': comandas_abiertas,
            },
            request=request,
        )
        if (
            turno.diferencia is not None
            and abs(turno.diferencia) > obtener_umbral('CAJA_MARGEN_DESCUADRE')
        ):
            AuditoriaService.registrar(
                usuario=usuario_auditoria,
                accion='CAJA_DESCUADRE_DETECTADO',
                modulo='CAJA',
                entidad='CAJA_TURNO',
                entidad_id=turno.id,
                severidad=AuditLog.Severidad.ADVERTENCIA,
                estado_resultado=AuditLog.EstadoResultado.EXITOSO,
                descripcion=f'Se detecto un descuadre en {turno.codigo_turno}.',
                valores_nuevos={'diferencia': str(turno.diferencia)},
                request=request,
                datos_contextuales={
                    'impacto_economico_estimado': abs(turno.diferencia),
                },
            )
        return turno

    @staticmethod
    @transaction.atomic
    def reabrir_turno(turno_id, usuario, motivo, request=None):
        motivo = str(motivo or '').strip()
        if not motivo:
            raise DatosInvalidos('El motivo es obligatorio para reabrir el turno.')
        if CajaTurno.objects.select_for_update().filter(
            estado=CajaTurno.Estado.ABIERTA
        ).exists():
            raise OperacionNoPermitida('Ya existe un turno de caja abierto.')
        try:
            turno = CajaTurno.objects.select_for_update().get(pk=turno_id)
        except CajaTurno.DoesNotExist:
            raise RecursoNoEncontrado('Turno de caja no encontrado.')
        if turno.estado != CajaTurno.Estado.CERRADA:
            raise OperacionNoPermitida('Solo se puede reabrir un turno cerrado.')
        turno.estado = CajaTurno.Estado.ABIERTA
        turno.fecha_cierre = None
        turno.saldo_final = None
        turno.arqueo_fisico = None
        turno.diferencia = None
        turno.save(update_fields=[
            'estado', 'fecha_cierre', 'saldo_final', 'arqueo_fisico', 'diferencia'
        ])
        AuditoriaService.registrar(
            usuario=usuario,
            accion='CAJA_TURNO_REABIERTO',
            modulo='CAJA',
            entidad='CAJA_TURNO',
            entidad_id=turno.id,
            severidad=AuditLog.Severidad.CRITICA,
            estado_resultado=AuditLog.EstadoResultado.EXITOSO,
            descripcion=f'Se reabrio el turno {turno.codigo_turno}.',
            motivo=motivo,
            valores_anteriores={'estado': CajaTurno.Estado.CERRADA},
            valores_nuevos={'estado': CajaTurno.Estado.ABIERTA},
            request=request,
        )
        return turno

    @staticmethod
    @transaction.atomic
    def modificar_metodo_pago(pago_id, metodo_pago_id, usuario, motivo='', request=None):
        try:
            pago = Pago.objects.select_for_update().select_related(
                'metodo_pago', 'caja_turno'
            ).get(pk=pago_id, activo=True)
            nuevo_metodo = MetodoPago.objects.get(pk=metodo_pago_id, activo=True)
        except Pago.DoesNotExist:
            raise RecursoNoEncontrado('Pago no encontrado.')
        except MetodoPago.DoesNotExist:
            raise RecursoNoEncontrado('Metodo de pago no encontrado.')
        anterior = pago.metodo_pago
        if anterior.id == nuevo_metodo.id:
            raise OperacionNoPermitida('El pago ya usa el metodo solicitado.')
        neto = pago.monto - pago.vuelto
        turno = pago.caja_turno
        if anterior.codigo == 'EFECTIVO':
            turno.total_efectivo -= neto
        else:
            turno.total_tarjeta -= neto
        if nuevo_metodo.codigo == 'EFECTIVO':
            turno.total_efectivo += neto
        else:
            turno.total_tarjeta += neto
        turno.save(update_fields=['total_efectivo', 'total_tarjeta'])
        pago.metodo_pago = nuevo_metodo
        pago.save(update_fields=['metodo_pago'])
        AuditoriaService.registrar(
            usuario=usuario,
            accion='PAGO_METODO_MODIFICADO',
            modulo='CAJA',
            entidad='PAGO',
            entidad_id=pago.id,
            severidad=AuditLog.Severidad.ADVERTENCIA,
            estado_resultado=AuditLog.EstadoResultado.EXITOSO,
            descripcion=f'Se modifico el metodo del pago {pago.id}.',
            motivo=str(motivo or '').strip() or None,
            valores_anteriores={'metodo_pago': anterior.codigo},
            valores_nuevos={'metodo_pago': nuevo_metodo.codigo},
            request=request,
        )
        return pago

    @staticmethod
    @transaction.atomic
    def anular_pago(pago_id, usuario, motivo, request=None):
        motivo = str(motivo or '').strip()
        if not motivo:
            raise DatosInvalidos('El motivo es obligatorio para anular un pago.')
        try:
            pago = Pago.objects.select_for_update().select_related(
                'metodo_pago', 'caja_turno'
            ).get(pk=pago_id, activo=True)
        except Pago.DoesNotExist:
            raise RecursoNoEncontrado('Pago no encontrado.')
        if pago.estado != Pago.Estado.PAGADO:
            raise OperacionNoPermitida('Solo se puede anular un pago confirmado.')
        turno = pago.caja_turno
        neto = pago.monto - pago.vuelto
        turno.total_ventas -= neto
        if pago.metodo_pago.codigo == 'EFECTIVO':
            turno.total_efectivo -= neto
        else:
            turno.total_tarjeta -= neto
        turno.save(update_fields=['total_ventas', 'total_efectivo', 'total_tarjeta'])
        pago.estado = Pago.Estado.ANULADO
        pago.save(update_fields=['estado'])
        AuditoriaService.registrar(
            usuario=usuario,
            accion='PAGO_ANULADO',
            modulo='CAJA',
            entidad='PAGO',
            entidad_id=pago.id,
            severidad=AuditLog.Severidad.CRITICA,
            estado_resultado=AuditLog.EstadoResultado.EXITOSO,
            descripcion=f'Se anulo el pago {pago.id}.',
            motivo=motivo,
            valores_anteriores={'estado': Pago.Estado.PAGADO},
            valores_nuevos={'estado': Pago.Estado.ANULADO},
            request=request,
            datos_contextuales={'impacto_economico_estimado': neto},
        )
        return pago

    @staticmethod
    @transaction.atomic
    def eliminar_pago(pago_id, usuario, motivo, request=None):
        motivo = str(motivo or '').strip()
        if not motivo:
            raise DatosInvalidos('El motivo es obligatorio para eliminar un pago.')
        try:
            pago = Pago.objects.select_for_update().get(pk=pago_id, activo=True)
        except Pago.DoesNotExist:
            raise RecursoNoEncontrado('Pago no encontrado.')
        if pago.estado != Pago.Estado.ANULADO:
            raise OperacionNoPermitida('Solo se puede eliminar logicamente un pago anulado.')
        pago.activo = False
        pago.save(update_fields=['activo'])
        AuditoriaService.registrar(
            usuario=usuario,
            accion='PAGO_SOFT_DELETE',
            modulo='CAJA',
            entidad='PAGO',
            entidad_id=pago.id,
            severidad=AuditLog.Severidad.ADVERTENCIA,
            estado_resultado=AuditLog.EstadoResultado.EXITOSO,
            descripcion=f'Se elimino logicamente el pago {pago.id}.',
            motivo=motivo,
            valores_anteriores={'activo': True},
            valores_nuevos={'activo': False},
            request=request,
        )
        return pago

    cobrar = staticmethod(procesar_cobro)
    registrar_perdida = staticmethod(registrar_perdida)
