"""Application services for menu categories, dishes, and recipes."""

import json
from decimal import Decimal, InvalidOperation

from django.db import transaction

from apps.auditoria.constants import obtener_umbral
from apps.auditoria.models import AuditLog
from apps.auditoria.services import AuditoriaService
from apps.core.exceptions import DatosInvalidos, OperacionNoPermitida, RecursoNoEncontrado
from apps.inventario.models import Insumo, RecetaInsumo

from .models import Categoria, Plato


class MenuService:
    """Coordinates menu writes and recipe consistency."""

    @staticmethod
    @transaction.atomic
    def guardar_categoria(serializer):
        return serializer.save()

    @staticmethod
    @transaction.atomic
    def desactivar_categoria(categoria):
        if categoria.platos.filter(activo=True).exists():
            raise OperacionNoPermitida(
                "No se puede desactivar una categoria con platos activos."
            )
        categoria.activo = False
        categoria.save(update_fields=["activo"])
        return categoria

    @staticmethod
    def _normalizar_receta(receta_data):
        normalizada = []
        for item in receta_data:
            if isinstance(item, str):
                try:
                    item = json.loads(item)
                except json.JSONDecodeError:
                    raise DatosInvalidos("La receta contiene JSON invalido.")
            if not isinstance(item, dict) or not item.get("insumo_id"):
                raise DatosInvalidos("Cada ingrediente debe indicar insumo_id.")
            try:
                cantidad = Decimal(str(item.get("cantidad_por_porcion", 0)))
                merma = Decimal(str(item.get("merma_porcentaje", 0)))
                insumo_id = int(item["insumo_id"])
            except (InvalidOperation, TypeError, ValueError):
                raise DatosInvalidos("Cantidad o merma invalida en la receta.")
            if cantidad <= 0 or merma < 0 or merma > 100:
                raise DatosInvalidos("La cantidad debe ser positiva y la merma estar entre 0 y 100.")
            normalizada.append((insumo_id, cantidad, merma, item.get("activo", True)))
        return normalizada

    @staticmethod
    def _snapshot_receta(plato):
        return [
            {
                'id': receta.id,
                'insumo_id': receta.insumo_id,
                'cantidad_por_porcion': str(receta.cantidad_por_porcion),
                'merma_porcentaje': str(receta.merma_porcentaje),
                'activo': receta.activo,
            }
            for receta in plato.receta.filter(activo=True).order_by('insumo_id')
        ]

    @staticmethod
    @transaction.atomic
    def guardar_plato(
        serializer, receta_data=None, usuario=None, motivo=None, request=None
    ):
        instancia = serializer.instance
        es_actualizacion = bool(instancia and instancia.pk)
        anterior = None
        receta_anterior = []
        if es_actualizacion:
            anterior = {
                'precio_actual': instancia.precio_actual,
                'disponible': instancia.disponible,
                'activo': instancia.activo,
            }
            receta_anterior = MenuService._snapshot_receta(instancia)
        motivo = str(motivo or '').strip()
        plato = serializer.save()
        if receta_data is not None:
            MenuService.asignar_receta(plato, receta_data)

        if not es_actualizacion or usuario is None:
            return plato

        receta_nueva = MenuService._snapshot_receta(plato)
        cambio_precio = anterior['precio_actual'] != plato.precio_actual
        cambio_receta = receta_anterior != receta_nueva
        if (cambio_precio or cambio_receta) and not motivo:
            raise DatosInvalidos('El motivo es obligatorio al cambiar precio o receta.')

        if cambio_precio:
            variacion = (
                abs(plato.precio_actual - anterior['precio_actual'])
                / anterior['precio_actual'] * Decimal('100')
                if anterior['precio_actual'] > 0 else Decimal('100')
            )
            accion = (
                'PLATO_CAMBIO_MASIVO_PRECIOS'
                if variacion > obtener_umbral('PRECIO_VARIACION_ALTA_PORCENTAJE')
                else 'PLATO_PRECIO_MODIFICADO'
            )
            AuditoriaService.registrar(
                usuario=usuario,
                accion=accion,
                modulo='MENU',
                entidad='PLATO',
                entidad_id=plato.id,
                severidad=(
                    AuditLog.Severidad.CRITICA
                    if accion == 'PLATO_CAMBIO_MASIVO_PRECIOS'
                    else AuditLog.Severidad.ADVERTENCIA
                ),
                estado_resultado=AuditLog.EstadoResultado.EXITOSO,
                descripcion=f'Se modifico el precio de {plato.nombre}.',
                motivo=motivo,
                valores_anteriores={
                    'precio_actual': str(anterior['precio_actual'])
                },
                valores_nuevos={
                    'precio_actual': str(plato.precio_actual),
                    'variacion_porcentaje': str(variacion),
                },
                request=request,
            )

        if cambio_receta:
            ids_anteriores = {item['insumo_id'] for item in receta_anterior}
            ids_nuevos = {item['insumo_id'] for item in receta_nueva}
            eliminados = ids_anteriores - ids_nuevos
            anterior_por_insumo = {
                item['insumo_id']: item for item in receta_anterior
            }
            nuevo_por_insumo = {
                item['insumo_id']: item for item in receta_nueva
            }
            if eliminados:
                AuditoriaService.registrar(
                    usuario=usuario,
                    accion='RECETA_INSUMO_ELIMINADO',
                    modulo='MENU',
                    entidad='PLATO',
                    entidad_id=plato.id,
                    severidad=AuditLog.Severidad.ADVERTENCIA,
                    estado_resultado=AuditLog.EstadoResultado.EXITOSO,
                    descripcion=f'Se eliminaron insumos de la receta de {plato.nombre}.',
                    motivo=motivo,
                    valores_anteriores={'insumos': sorted(ids_anteriores)},
                    valores_nuevos={'insumos_eliminados': sorted(eliminados)},
                    request=request,
                )
            ingredientes_modificados = any(
                anterior_por_insumo[insumo_id] != nuevo_por_insumo[insumo_id]
                for insumo_id in ids_anteriores & ids_nuevos
            )
            if ids_nuevos - ids_anteriores or ingredientes_modificados:
                AuditoriaService.registrar(
                    usuario=usuario,
                    accion='RECETA_MODIFICADA',
                    modulo='MENU',
                    entidad='PLATO',
                    entidad_id=plato.id,
                    severidad=AuditLog.Severidad.ADVERTENCIA,
                    estado_resultado=AuditLog.EstadoResultado.EXITOSO,
                    descripcion=f'Se modifico la receta de {plato.nombre}.',
                    motivo=motivo,
                    valores_anteriores={'receta': receta_anterior},
                    valores_nuevos={'receta': receta_nueva},
                    request=request,
                )

        if not anterior['disponible'] and plato.disponible:
            from apps.inventario.services import verificar_disponibilidad_plato
            disponible, detalle = verificar_disponibilidad_plato(plato)
            if not disponible:
                AuditoriaService.registrar(
                    usuario=usuario,
                    accion='PLATO_REACTIVADO_SIN_STOCK',
                    modulo='MENU',
                    entidad='PLATO',
                    entidad_id=plato.id,
                    severidad=AuditLog.Severidad.CRITICA,
                    estado_resultado=AuditLog.EstadoResultado.EXITOSO,
                    descripcion=f'Se intento reactivar {plato.nombre} sin stock suficiente.',
                    valores_anteriores={'disponible': False},
                    valores_nuevos={'disponible_solicitado': True, 'motivo': detalle},
                    request=request,
                    deduplicar_alerta=True,
                )
                plato.disponible = False
                plato.save(update_fields=['disponible'])
            else:
                AuditoriaService.resolver_alerta(
                    accion='PLATO_REACTIVADO_SIN_STOCK',
                    entidad='PLATO', entidad_id=plato.id,
                )
        return plato

    @staticmethod
    @transaction.atomic
    def asignar_receta(plato, receta_data):
        receta = MenuService._normalizar_receta(receta_data)
        insumo_ids = {item[0] for item in receta}
        existentes = set(
            Insumo.objects.filter(pk__in=insumo_ids, activo=True).values_list("id", flat=True)
        )
        if existentes != insumo_ids:
            raise RecursoNoEncontrado("Uno o mas insumos no existen o estan inactivos.")
        for insumo_id, cantidad, merma, activo in receta:
            RecetaInsumo.objects.update_or_create(
                plato=plato,
                insumo_id=insumo_id,
                defaults={
                    "cantidad_por_porcion": cantidad,
                    "merma_porcentaje": merma,
                    "activo": activo,
                },
            )
        plato.receta.exclude(insumo_id__in=insumo_ids).update(activo=False)
        return plato

    @staticmethod
    @transaction.atomic
    def desactivar_plato(plato, usuario=None, motivo=None, request=None):
        anterior = {'activo': plato.activo, 'disponible': plato.disponible}
        motivo = str(motivo or '').strip()
        if usuario is not None and not motivo:
            raise DatosInvalidos('El motivo es obligatorio para desactivar un plato.')
        plato.activo = False
        plato.disponible = False
        plato.save(update_fields=["activo", "disponible"])
        plato.receta.filter(activo=True).update(activo=False)
        if usuario is not None:
            AuditoriaService.registrar(
                usuario=usuario,
                accion='PLATO_SOFT_DELETE',
                modulo='MENU',
                entidad='PLATO',
                entidad_id=plato.id,
                severidad=AuditLog.Severidad.ADVERTENCIA,
                estado_resultado=AuditLog.EstadoResultado.EXITOSO,
                descripcion=f'Se desactivo el plato {plato.nombre}.',
                motivo=motivo,
                valores_anteriores=anterior,
                valores_nuevos={'activo': False, 'disponible': False},
                request=request,
            )
        return plato

    @staticmethod
    @transaction.atomic
    def agregar_insumo(plato, data, usuario=None, motivo=None, request=None):
        try:
            insumo_id = int(data.get("insumo_id"))
            cantidad = Decimal(str(data.get("cantidad_por_porcion")))
            merma = Decimal(str(data.get("merma_porcentaje", 0)))
        except (TypeError, ValueError, InvalidOperation):
            raise DatosInvalidos("Insumo, cantidad o merma invalidos.")
        if cantidad <= 0:
            raise DatosInvalidos("La cantidad debe ser mayor a cero.")
        if not Insumo.objects.filter(pk=insumo_id, activo=True).exists():
            raise RecursoNoEncontrado("Insumo no encontrado.")
        existente = RecetaInsumo.objects.filter(
            plato=plato, insumo_id=insumo_id
        ).first()
        anterior = (
            {
                'cantidad_por_porcion': str(existente.cantidad_por_porcion),
                'merma_porcentaje': str(existente.merma_porcentaje),
                'activo': existente.activo,
            } if existente else None
        )
        motivo = str(motivo or '').strip()
        if usuario is not None and not motivo:
            raise DatosInvalidos('El motivo es obligatorio al cambiar una receta.')
        receta, _ = RecetaInsumo.objects.update_or_create(
            plato=plato,
            insumo_id=insumo_id,
            defaults={
                "cantidad_por_porcion": cantidad,
                "merma_porcentaje": merma,
                "activo": True,
            },
        )
        if usuario is not None:
            AuditoriaService.registrar(
                usuario=usuario,
                accion='RECETA_MODIFICADA',
                modulo='MENU',
                entidad='PLATO',
                entidad_id=plato.id,
                severidad=AuditLog.Severidad.ADVERTENCIA,
                estado_resultado=AuditLog.EstadoResultado.EXITOSO,
                descripcion=f'Se modifico la receta de {plato.nombre}.',
                motivo=motivo,
                valores_anteriores={'ingrediente': anterior},
                valores_nuevos={
                    'insumo_id': insumo_id,
                    'cantidad_por_porcion': str(cantidad),
                    'merma_porcentaje': str(merma),
                    'activo': True,
                },
                request=request,
            )
        return receta

    @staticmethod
    @transaction.atomic
    def eliminar_insumo(
        plato, insumo_id, usuario=None, motivo=None, request=None
    ):
        try:
            receta = plato.receta.get(insumo_id=insumo_id, activo=True)
        except RecetaInsumo.DoesNotExist:
            raise RecursoNoEncontrado("Insumo no encontrado en este plato.")
        motivo = str(motivo or '').strip()
        if usuario is not None and not motivo:
            raise DatosInvalidos('El motivo es obligatorio al eliminar un insumo.')
        anterior = {
            'insumo_id': receta.insumo_id,
            'cantidad_por_porcion': str(receta.cantidad_por_porcion),
            'merma_porcentaje': str(receta.merma_porcentaje),
            'activo': True,
        }
        receta.activo = False
        receta.save(update_fields=["activo"])
        if usuario is not None:
            AuditoriaService.registrar(
                usuario=usuario,
                accion='RECETA_INSUMO_ELIMINADO',
                modulo='MENU',
                entidad='PLATO',
                entidad_id=plato.id,
                severidad=AuditLog.Severidad.ADVERTENCIA,
                estado_resultado=AuditLog.EstadoResultado.EXITOSO,
                descripcion=f'Se elimino un insumo de la receta de {plato.nombre}.',
                motivo=motivo,
                valores_anteriores=anterior,
                valores_nuevos={'activo': False},
                request=request,
            )
        return receta

    @staticmethod
    @transaction.atomic
    def actualizar_precios_masivos(cambios, usuario, motivo, request=None):
        motivo = str(motivo or '').strip()
        if not motivo:
            raise DatosInvalidos('El motivo es obligatorio al cambiar precios.')
        if len(cambios) < obtener_umbral('PRECIO_CAMBIO_MASIVO_CANTIDAD'):
            raise DatosInvalidos('La operacion no contiene varios platos.')
        ids = [int(cambio['plato_id']) for cambio in cambios]
        platos = {
            plato.id: plato
            for plato in Plato.objects.select_for_update().filter(pk__in=ids, activo=True)
        }
        if len(platos) != len(set(ids)):
            raise RecursoNoEncontrado('Uno o mas platos no existen.')
        anteriores = {}
        nuevos = {}
        for cambio in cambios:
            plato = platos[int(cambio['plato_id'])]
            precio = Decimal(str(cambio['precio_actual']))
            if precio <= 0:
                raise DatosInvalidos('El precio debe ser mayor a cero.')
            anteriores[str(plato.id)] = str(plato.precio_actual)
            nuevos[str(plato.id)] = str(precio)
            plato.precio_actual = precio
        Plato.objects.bulk_update(platos.values(), ['precio_actual'])
        AuditoriaService.registrar(
            usuario=usuario,
            accion='PLATO_CAMBIO_MASIVO_PRECIOS',
            modulo='MENU',
            entidad='LOTE_PRECIOS',
            entidad_id=min(ids),
            severidad=AuditLog.Severidad.CRITICA,
            estado_resultado=AuditLog.EstadoResultado.EXITOSO,
            descripcion=f'Se modificaron los precios de {len(platos)} platos.',
            motivo=motivo,
            valores_anteriores={'precios': anteriores},
            valores_nuevos={'precios': nuevos, 'cantidad': len(platos)},
            request=request,
        )
        return list(platos.values())
