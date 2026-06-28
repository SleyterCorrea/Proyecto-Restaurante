"""Application services for orders and kitchen workflow."""

import logging
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from uuid import uuid4

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import transaction
from django.utils import timezone

from apps.core.exceptions import (
    DatosInvalidos,
    MesaConComandaActiva,
    OperacionNoPermitida,
    RecursoNoEncontrado,
    StockInsuficiente,
    TransicionEstadoInvalida,
)
from apps.inventario.models import RecetaInsumo
from apps.menu.models import Plato
from apps.mesas.models import Mesa

from .models import Comanda, ComandaHistorialEstado, LineaComanda

logger = logging.getLogger(__name__)


def _emitir_kds(action, detail):
    try:
        async_to_sync(get_channel_layer().group_send)(
            "kds_updates",
            {"type": "kds_update", "action": action, "detail": detail},
        )
    except Exception:
        logger.exception("No se pudo emitir la actualizacion KDS: %s", action)


class ComandaService:
    """Coordinates the dining-room order lifecycle."""

    ESTADOS_ACTIVOS = (
        Comanda.Estado.ABIERTA,
        Comanda.Estado.EN_PREPARACION,
        Comanda.Estado.LISTA,
    )

    @staticmethod
    def _normalizar_mesas(data):
        mesa_ids = list(data.get("mesa_ids") or [])
        if not mesa_ids and data.get("mesa_id"):
            mesa_ids = [data["mesa_id"]]
        try:
            mesa_ids = [int(pk) for pk in dict.fromkeys(mesa_ids)]
        except (TypeError, ValueError):
            raise DatosInvalidos("Los identificadores de mesa no son validos.")
        if not mesa_ids:
            raise DatosInvalidos("Falta el campo mesa_ids.")
        if len(mesa_ids) > 3:
            raise DatosInvalidos("Máximo 3 mesas permitidas.")
        return mesa_ids

    @staticmethod
    def _normalizar_items(items):
        if not items:
            raise DatosInvalidos("El pedido no tiene items.")
        normalizados = []
        for item in items:
            try:
                plato_id = int(item.get("plato_id"))
                cantidad = int(item.get("cantidad", 1))
            except (TypeError, ValueError):
                raise DatosInvalidos("El pedido contiene un item invalido.")
            if cantidad < 1:
                raise DatosInvalidos("La cantidad debe ser mayor a cero.")
            normalizados.append({
                "plato_id": plato_id,
                "cantidad": cantidad,
                "notas": item.get("notas", ""),
            })
        return normalizados

    @staticmethod
    def _cargar_platos_y_validar_stock(items):
        plato_ids = {item["plato_id"] for item in items}
        platos = {
            plato.id: plato
            for plato in Plato.objects.filter(pk__in=plato_ids, activo=True)
        }
        if len(platos) != len(plato_ids):
            raise RecursoNoEncontrado("Uno de los platos indicados no existe.")

        requerimientos = defaultdict(Decimal)
        recetas = RecetaInsumo.objects.filter(
            plato_id__in=plato_ids, activo=True
        ).select_related("insumo")
        recetas_por_plato = defaultdict(list)
        for receta in recetas:
            recetas_por_plato[receta.plato_id].append(receta)

        for item in items:
            plato = platos[item["plato_id"]]
            for receta in recetas_por_plato[plato.id]:
                requerimientos[receta.insumo_id] += (
                    receta.cantidad_por_porcion * item["cantidad"]
                )

        insumos = {receta.insumo_id: receta.insumo for receta in recetas}
        for insumo_id, requerido in requerimientos.items():
            insumo = insumos[insumo_id]
            if not insumo.activo or insumo.stock_real < requerido:
                raise StockInsuficiente(insumo.nombre, insumo.stock_real, requerido)
        for item in items:
            plato = platos[item["plato_id"]]
            if not plato.disponible:
                raise OperacionNoPermitida(f'El plato "{plato.nombre}" no está disponible.')
        return platos

    @classmethod
    @transaction.atomic
    def abrir(cls, data, usuario):
        mesa_ids = cls._normalizar_mesas(data)
        items = cls._normalizar_items(data.get("items", []))

        mesas_map = {
            mesa.id: mesa
            for mesa in Mesa.objects.select_for_update().filter(pk__in=mesa_ids, activo=True)
        }
        if len(mesas_map) != len(mesa_ids):
            raise RecursoNoEncontrado("Una o mas mesas no fueron encontradas.")
        mesas = [mesas_map[pk] for pk in mesa_ids]

        ocupadas = [mesa for mesa in mesas if mesa.estado != Mesa.Estado.LIBRE]
        # The row locks above serialize changes to every selected table.
        if ocupadas:
            mesa = ocupadas[0]
            raise MesaConComandaActiva(
                f"La mesa {mesa.numero} no está libre (estado: {mesa.get_estado_display()})."
            )
        if Comanda.objects.filter(
            mesa_id__in=mesa_ids, estado__in=cls.ESTADOS_ACTIVOS
        ).exists() or Comanda.objects.filter(
            mesas_adicionales__id__in=mesa_ids, estado__in=cls.ESTADOS_ACTIVOS
        ).exists():
            raise MesaConComandaActiva("Una de las mesas ya tiene una comanda activa.")

        platos = cls._cargar_platos_y_validar_stock(items)
        ahora = timezone.now()
        codigo = f"COM-{ahora:%Y%m%d}-{uuid4().hex[:8].upper()}"
        comanda = Comanda.objects.create(
            codigo_comanda=codigo,
            mesa=mesas[0],
            mozo=usuario,
            nombre_cliente=data.get("nombre_cliente", ""),
            estado=Comanda.Estado.ABIERTA,
            observacion_general=data.get("notas", ""),
        )
        if len(mesas) > 1:
            comanda.mesas_adicionales.set(mesas[1:])

        lineas = [
            LineaComanda(
                comanda=comanda,
                plato=platos[item["plato_id"]],
                cantidad=item["cantidad"],
                precio_unitario=platos[item["plato_id"]].precio_actual,
                subtotal=platos[item["plato_id"]].precio_actual * item["cantidad"],
                observacion=item["notas"],
                fecha_envio_cocina=ahora,
                tiempo_estimado_min=platos[item["plato_id"]].tiempo_preparacion_min or 0,
            )
            for item in items
        ]
        LineaComanda.objects.bulk_create(lineas)
        Mesa.objects.filter(pk__in=mesa_ids).update(estado=Mesa.Estado.OCUPADA)
        comanda.calcular_totales()
        transaction.on_commit(
            lambda: _emitir_kds(
                "nueva_comanda", {"comanda_id": comanda.id, "mesa": mesas[0].numero}
            )
        )
        return comanda

    @classmethod
    @transaction.atomic
    def agregar_plato(cls, comanda_id, data):
        try:
            comanda = Comanda.objects.select_for_update().get(pk=comanda_id)
        except Comanda.DoesNotExist:
            raise RecursoNoEncontrado("Comanda no encontrada.")
        if comanda.estado not in (Comanda.Estado.ABIERTA, Comanda.Estado.EN_PREPARACION):
            raise OperacionNoPermitida("No se pueden agregar platos en el estado actual.")
        items = cls._normalizar_items([data])
        platos = cls._cargar_platos_y_validar_stock(items)
        item = items[0]
        plato = platos[item["plato_id"]]
        linea = LineaComanda.objects.create(
            comanda=comanda,
            plato=plato,
            cantidad=item["cantidad"],
            precio_unitario=plato.precio_actual,
            subtotal=plato.precio_actual * item["cantidad"],
            observacion=item["notas"],
            fecha_envio_cocina=timezone.now(),
            tiempo_estimado_min=plato.tiempo_preparacion_min or 0,
        )
        comanda.calcular_totales()
        transaction.on_commit(
            lambda: _emitir_kds("nueva_linea", {"comanda_id": comanda.id})
        )
        return linea

    @staticmethod
    @transaction.atomic
    def editar_linea(linea_id, data):
        try:
            linea = LineaComanda.objects.select_for_update().select_related("comanda", "plato").get(pk=linea_id)
        except LineaComanda.DoesNotExist:
            raise RecursoNoEncontrado("Linea no encontrada.")
        if linea.estado != LineaComanda.Estado.PENDIENTE:
            raise OperacionNoPermitida(
                f"No se puede modificar: el plato ya esta {linea.get_estado_display().upper()}."
            )
        if "plato_id" in data:
            try:
                linea.plato = Plato.objects.get(pk=data["plato_id"], activo=True)
            except Plato.DoesNotExist:
                raise RecursoNoEncontrado("El plato seleccionado no existe.")
            linea.precio_unitario = linea.plato.precio_actual
        if "cantidad" in data:
            try:
                cantidad = int(data["cantidad"])
            except (TypeError, ValueError):
                raise DatosInvalidos("La cantidad no es valida.")
            if cantidad < 1:
                raise DatosInvalidos("La cantidad debe ser mayor a cero.")
            linea.cantidad = cantidad
        if "notas" in data:
            linea.observacion = data["notas"]
        ComandaService._cargar_platos_y_validar_stock([{
            "plato_id": linea.plato_id, "cantidad": linea.cantidad, "notas": linea.observacion or ""
        }])
        linea.subtotal = linea.precio_unitario * linea.cantidad
        linea.save()
        linea.comanda.calcular_totales()
        return linea

    @staticmethod
    @transaction.atomic
    def eliminar_linea(linea_id):
        try:
            linea = LineaComanda.objects.select_for_update().select_related("comanda").get(pk=linea_id)
        except LineaComanda.DoesNotExist:
            raise RecursoNoEncontrado("Linea no encontrada.")
        if linea.estado != LineaComanda.Estado.PENDIENTE:
            raise OperacionNoPermitida("Solo se pueden eliminar platos pendientes.")
        comanda = linea.comanda
        linea.delete()
        comanda.calcular_totales()
        if not comanda.lineas.exists():
            comanda.estado = Comanda.Estado.ANULADA
            comanda.save(update_fields=["estado"])
            Mesa.objects.filter(pk__in=[mesa.pk for mesa in comanda.todas_las_mesas]).update(
                estado=Mesa.Estado.LIBRE
            )

    @staticmethod
    @transaction.atomic
    def marcar_entregado(comanda_id):
        try:
            comanda = Comanda.objects.select_for_update().get(pk=comanda_id)
        except Comanda.DoesNotExist:
            raise RecursoNoEncontrado("Comanda no encontrada.")
        lineas = comanda.lineas.filter(estado=LineaComanda.Estado.LISTO)
        cantidad = lineas.count()
        if not cantidad:
            raise OperacionNoPermitida("No hay platos listos pendientes de entrega.")
        lineas.update(estado=LineaComanda.Estado.ENTREGADO, fecha_entregado=timezone.now())
        comanda.marcar_como_lista()
        return cantidad

    @classmethod
    @transaction.atomic
    def enviar_a_caja(cls, mesa_id):
        try:
            mesa = Mesa.objects.select_for_update().get(pk=mesa_id)
        except Mesa.DoesNotExist:
            raise RecursoNoEncontrado("Mesa no encontrada.")
        from django.db.models import Q
        comanda = Comanda.objects.select_for_update(of=('self',)).filter(
            Q(mesa=mesa) | Q(mesas_adicionales=mesa), estado__in=cls.ESTADOS_ACTIVOS
        ).order_by("-fecha_apertura").first()
        if not comanda:
            raise OperacionNoPermitida("No hay comanda activa en esta mesa.")
        if comanda.lineas.exclude(
            estado__in=(LineaComanda.Estado.LISTO, LineaComanda.Estado.ENTREGADO, LineaComanda.Estado.ANULADO)
        ).exists():
            raise OperacionNoPermitida("Aun hay platos pendientes en cocina.")
        comanda.estado = Comanda.Estado.LISTA
        comanda.save(update_fields=["estado"])
        Mesa.objects.filter(pk__in=[m.pk for m in comanda.todas_las_mesas]).update(
            estado=Mesa.Estado.POR_PAGAR
        )
        return comanda


class CocinaService:
    """Coordinates kitchen state transitions and audit records."""

    TRANSICIONES = {
        LineaComanda.Estado.PENDIENTE: (LineaComanda.Estado.EN_PREP, LineaComanda.Estado.ANULADO),
        LineaComanda.Estado.EN_PREP: (LineaComanda.Estado.LISTO, LineaComanda.Estado.ANULADO),
        LineaComanda.Estado.LISTO: (LineaComanda.Estado.ANULADO,),
    }

    @staticmethod
    @transaction.atomic
    def cambiar_estado(linea_id, nuevo_estado, usuario, motivo="", cantidad_parcial=0):
        try:
            linea = LineaComanda.objects.select_for_update().select_related(
                "plato", "comanda", "comanda__mesa"
            ).get(pk=linea_id)
        except LineaComanda.DoesNotExist:
            raise RecursoNoEncontrado("Linea no encontrada.")
        anterior = linea.estado
        if nuevo_estado not in CocinaService.TRANSICIONES.get(anterior, ()):
            raise TransicionEstadoInvalida(f"No se puede pasar de {anterior} a {nuevo_estado}.")
        if nuevo_estado == LineaComanda.Estado.ANULADO and not motivo:
            raise DatosInvalidos("Se requiere un motivo para anular.")

        ahora = timezone.now()
        if nuevo_estado == LineaComanda.Estado.EN_PREP:
            linea.fecha_inicio_prep = ahora
            if linea.comanda.estado == Comanda.Estado.ABIERTA:
                linea.comanda.estado = Comanda.Estado.EN_PREPARACION
                linea.comanda.save(update_fields=["estado"])
        elif nuevo_estado == LineaComanda.Estado.LISTO:
            linea.fecha_listo = ahora
            if linea.fecha_inicio_prep:
                linea.tiempo_real_preparacion_seg = int((ahora - linea.fecha_inicio_prep).total_seconds())

        nueva_linea = None
        if nuevo_estado == LineaComanda.Estado.ANULADO:
            linea.motivo_anulacion = motivo
            if cantidad_parcial:
                if cantidad_parcial < 1 or cantidad_parcial >= linea.cantidad:
                    raise DatosInvalidos("La cantidad parcial debe ser menor a la cantidad original.")
                linea.cantidad_parcial_cocina = cantidad_parcial
                nueva_linea = LineaComanda.objects.create(
                    comanda=linea.comanda,
                    plato=linea.plato,
                    cantidad=cantidad_parcial,
                    precio_unitario=linea.precio_unitario,
                    subtotal=linea.precio_unitario * cantidad_parcial,
                    observacion=linea.observacion,
                    estado=LineaComanda.Estado.EN_PREP,
                    fecha_envio_cocina=linea.fecha_envio_cocina,
                    fecha_inicio_prep=ahora,
                    tiempo_estimado_min=linea.tiempo_estimado_min,
                )
        linea.estado = nuevo_estado
        linea.save()
        linea.comanda.calcular_totales()
        ComandaHistorialEstado.objects.create(
            comanda=linea.comanda,
            estado_anterior=anterior,
            estado_nuevo=nuevo_estado,
            usuario=usuario,
            motivo=motivo or "Cambio de estado via KDS",
            origen=ComandaHistorialEstado.Origen.KDS,
        )
        linea.comanda.marcar_como_lista()
        transaction.on_commit(
            lambda: _emitir_kds("estado_cambiado", {"linea_id": linea_id, "nuevo_estado": nuevo_estado})
        )
        return linea, nueva_linea
