"""Application services for tables and table groups."""

from django.db import transaction
from django.db.models import Q

from apps.core.exceptions import DatosInvalidos, OperacionNoPermitida, RecursoNoEncontrado

from .models import Mesa, UnionMesas, Zona


class MesaService:
    """Coordinates table lifecycle and unions."""

    @staticmethod
    @transaction.atomic
    def crear(data):
        try:
            numero = int(data.get("numero"))
            capacidad = int(data.get("capacidad", 4))
            zona_id = int(data.get("zona_id"))
        except (TypeError, ValueError):
            raise DatosInvalidos("Numero, capacidad y zona son obligatorios.")
        if numero < 1 or capacidad < 1:
            raise DatosInvalidos("Numero y capacidad deben ser mayores a cero.")
        if not Zona.objects.filter(pk=zona_id, activo=True).exists():
            raise RecursoNoEncontrado("Zona no encontrada.")
        if Mesa.objects.filter(numero=numero, zona_id=zona_id, activo=True).exists():
            raise OperacionNoPermitida(f"La mesa {numero} ya existe en esa zona.")
        return Mesa.objects.create(
            numero=numero,
            capacidad=capacidad,
            zona_id=zona_id,
            estado=Mesa.Estado.LIBRE,
            activo=True,
        )

    @staticmethod
    @transaction.atomic
    def desactivar(mesa_id):
        try:
            mesa = Mesa.objects.select_for_update().get(pk=mesa_id, activo=True)
        except Mesa.DoesNotExist:
            raise RecursoNoEncontrado("La mesa no existe.")
        if mesa.estado != Mesa.Estado.LIBRE:
            raise OperacionNoPermitida("No se puede desactivar una mesa que no esta libre.")
        if UnionMesas.objects.filter(
            Q(mesa_principal=mesa) | Q(mesas_secundarias=mesa), activa=True
        ).exists():
            raise OperacionNoPermitida("La mesa pertenece a una union activa.")
        mesa.activo = False
        mesa.save(update_fields=["activo"])
        return mesa

    @staticmethod
    @transaction.atomic
    def crear_union(data):
        try:
            principal_id = int(data.get("mesa_principal_id"))
            secundarias_ids = [int(pk) for pk in data.get("mesa_secundaria_ids", [])]
        except (TypeError, ValueError):
            raise DatosInvalidos("Los identificadores de mesa no son validos.")
        ids = list(dict.fromkeys([principal_id] + secundarias_ids))
        if len(ids) < 2 or len(ids) > 3 or principal_id in secundarias_ids:
            raise DatosInvalidos("La union debe contener entre 2 y 3 mesas diferentes.")
        mesas = {
            mesa.id: mesa
            for mesa in Mesa.objects.select_for_update().filter(pk__in=ids, activo=True)
        }
        if len(mesas) != len(ids):
            raise RecursoNoEncontrado("Una o mas mesas no existen.")
        for mesa in mesas.values():
            if mesa.estado != Mesa.Estado.LIBRE:
                raise OperacionNoPermitida(f"La mesa {mesa.numero} no esta libre.")
            if UnionMesas.objects.filter(
                Q(mesa_principal=mesa) | Q(mesas_secundarias=mesa), activa=True
            ).exists():
                raise OperacionNoPermitida(f"La mesa {mesa.numero} ya pertenece a una union.")
        capacidad = data.get("capacidad_personalizada")
        if capacidad not in (None, ""):
            try:
                capacidad = int(capacidad)
            except ValueError:
                raise DatosInvalidos("La capacidad personalizada no es valida.")
            if capacidad < 1:
                raise DatosInvalidos("La capacidad debe ser mayor a cero.")
        else:
            capacidad = None
        union = UnionMesas.objects.create(
            mesa_principal=mesas[principal_id],
            activa=True,
            capacidad_personalizada=capacidad,
        )
        union.mesas_secundarias.set([mesas[pk] for pk in secundarias_ids])
        return union

    @staticmethod
    @transaction.atomic
    def disolver_union(union_id):
        try:
            union = UnionMesas.objects.select_for_update().get(pk=union_id, activa=True)
        except UnionMesas.DoesNotExist:
            raise RecursoNoEncontrado("Union no encontrada o ya disuelta.")
        if any(mesa.estado != Mesa.Estado.LIBRE for mesa in union.todas_las_mesas):
            raise OperacionNoPermitida("No se puede disolver una union con mesas ocupadas.")
        union.activa = False
        union.save(update_fields=["activa"])
        return union

    @staticmethod
    @transaction.atomic
    def marcar_limpiada(mesa_id):
        try:
            mesa = Mesa.objects.select_for_update().get(pk=mesa_id, activo=True)
        except Mesa.DoesNotExist:
            raise RecursoNoEncontrado("Mesa no encontrada.")
        if mesa.estado != Mesa.Estado.LIMPIEZA:
            raise OperacionNoPermitida("La mesa no esta en limpieza.")
        mesa.estado = Mesa.Estado.LIBRE
        mesa.save(update_fields=["estado"])
        return mesa
