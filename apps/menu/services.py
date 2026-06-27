"""Application services for menu categories, dishes, and recipes."""

import json
from decimal import Decimal, InvalidOperation

from django.db import transaction

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
    @transaction.atomic
    def guardar_plato(serializer, receta_data=None):
        plato = serializer.save()
        if receta_data is not None:
            MenuService.asignar_receta(plato, receta_data)
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
    def desactivar_plato(plato):
        plato.activo = False
        plato.disponible = False
        plato.save(update_fields=["activo", "disponible"])
        plato.receta.filter(activo=True).update(activo=False)
        return plato

    @staticmethod
    @transaction.atomic
    def agregar_insumo(plato, data):
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
        receta, _ = RecetaInsumo.objects.update_or_create(
            plato=plato,
            insumo_id=insumo_id,
            defaults={
                "cantidad_por_porcion": cantidad,
                "merma_porcentaje": merma,
                "activo": True,
            },
        )
        return receta

    @staticmethod
    @transaction.atomic
    def eliminar_insumo(plato, insumo_id):
        try:
            receta = plato.receta.get(insumo_id=insumo_id, activo=True)
        except RecetaInsumo.DoesNotExist:
            raise RecursoNoEncontrado("Insumo no encontrado en este plato.")
        receta.activo = False
        receta.save(update_fields=["activo"])
        return receta
