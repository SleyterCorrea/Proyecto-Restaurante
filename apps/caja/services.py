"""
Servicios de negocio para el módulo Caja (versión completa CAJA).

Incluye:
- procesar_cobro(): procesamiento atómico de cobros, multi-pago, cobro parcial por líneas.
- registrar_perdida(): marcar una comanda como pérdida (no pagó).
"""
import uuid
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError

from .models import CajaTurno, Pago, MetodoPago
from apps.mesas.models import Mesa
from apps.comandas.models import Comanda, LineaComanda


def _obtener_turno_activo():
    """Devuelve el CajaTurno abierto o lanza ValidationError."""
    turno = CajaTurno.objects.filter(estado=CajaTurno.Estado.ABIERTA).first()
    if not turno:
        raise ValidationError("No hay un turno de caja abierto. Abrí el turno antes de cobrar.")
    return turno


def _liberar_mesas_comanda(comanda):
    """Cambia todas las mesas de la comanda a estado LIMPIEZA."""
    for m in comanda.todas_las_mesas:
        m.estado = Mesa.Estado.LIMPIEZA
        m.save(update_fields=['estado'])


def procesar_cobro(comanda_id, pagos_data, usuario, linea_ids=None, observacion=None):
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
            raise ValidationError("La comanda no existe.")

        if comanda.estado == Comanda.Estado.COBRADA:
            raise ValidationError("Esta comanda ya fue cobrada.")

        if comanda.estado not in [Comanda.Estado.LISTA, Comanda.Estado.ABIERTA]:
            raise ValidationError(
                f"La comanda no está disponible para cobrar. Estado: {comanda.get_estado_display()}"
            )

        # Determinar las líneas a cobrar
        if linea_ids:
            lineas = list(comanda.lineas.filter(pk__in=linea_ids).select_related('plato'))
        else:
            lineas = list(comanda.lineas.exclude(estado=LineaComanda.Estado.ANULADO).select_related('plato'))

        if not lineas:
            raise ValidationError("No hay líneas válidas para cobrar.")

        # Calcular el total a cobrar según las líneas seleccionadas
        total_a_cobrar = sum(l.subtotal for l in lineas)

        # Validar que la suma de los pagos cubra el total
        total_pagado = sum(Decimal(str(p.get('monto', 0))) for p in pagos_data)
        if total_pagado < total_a_cobrar:
            raise ValidationError(
                f"El monto total pagado (S/. {total_pagado}) es insuficiente para cubrir S/. {total_a_cobrar}."
            )

        # Generar un ID de transacción único para agrupar todos los pagos de este cobro
        transaccion_id = str(uuid.uuid4())[:8].upper()

        pagos_creados = []
        metodos_usados = []

        for i, p_data in enumerate(pagos_data):
            metodo = MetodoPago.objects.get(pk=p_data['metodo_pago_id'])
            monto_pago = Decimal(str(p_data.get('monto', 0)))

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
                referencia=p_data.get('referencia', ''),
                transaccion_id=transaccion_id,
                estado=Pago.Estado.PAGADO,
                observacion=observacion or '',
            )

            # Asociar las líneas pagadas (M2M)
            pago.lineas_pagadas.set(lineas)
            pagos_creados.append(pago)
            metodos_usados.append(metodo)

        # Actualizar estado de la comanda
        comanda.estado = Comanda.Estado.COBRADA
        comanda.fecha_cierre = timezone.now()
        comanda.save(update_fields=['estado', 'fecha_cierre'])

        # Liberar mesas
        _liberar_mesas_comanda(comanda)

        # Actualizar totales del turno
        for i, pago in enumerate(pagos_creados):
            metodo = metodos_usados[i]
            turno.total_ventas += pago.monto
            if metodo.codigo == 'EFECTIVO':
                turno.total_efectivo += pago.monto
            else:
                turno.total_tarjeta += pago.monto

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


def registrar_perdida(comanda_id, usuario, observacion):
    """
    Marca una comanda como pérdida (el cliente no pagó o se fue).
    """
    with transaction.atomic():
        turno = _obtener_turno_activo()

        try:
            comanda = Comanda.objects.select_for_update().get(pk=comanda_id)
        except Comanda.DoesNotExist:
            raise ValidationError("La comanda no existe.")

        if comanda.estado == Comanda.Estado.COBRADA:
            raise ValidationError("Esta comanda ya fue cobrada.")

        # Usar el primer método de pago disponible (o crear uno genérico)
        metodo_perdida = MetodoPago.objects.filter(codigo='PERDIDA', activo=True).first()
        if not metodo_perdida:
            # Si no existe el método PERDIDA, usar el primer método disponible
            metodo_perdida = MetodoPago.objects.filter(activo=True).first()
            if not metodo_perdida:
                raise ValidationError("No hay métodos de pago disponibles.")

        pago = Pago.objects.create(
            caja_turno=turno,
            comanda=comanda,
            metodo_pago=metodo_perdida,
            monto=comanda.total,
            vuelto=Decimal('0'),
            estado=Pago.Estado.PERDIDA,
            observacion=observacion or 'Cliente no pagó',
        )

        # Marcar como COBRADA aunque sea pérdida (para que no quede abierta)
        comanda.estado = Comanda.Estado.COBRADA
        comanda.fecha_cierre = timezone.now()
        comanda.save(update_fields=['estado', 'fecha_cierre'])

        _liberar_mesas_comanda(comanda)

        return pago
