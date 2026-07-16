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
        zonas = {mesa.zona_id for mesa in mesas.values()}
        if len(zonas) > 1:
            raise OperacionNoPermitida(
                "Solo se pueden unir mesas pertenecientes a una misma zona."
            )

        # Buscar si alguna de estas mesas ya pertenece a una unión activa
        uniones_activas = list(UnionMesas.objects.filter(
            Q(mesa_principal__in=ids) | Q(mesas_secundarias__in=ids), activa=True
        ).distinct().prefetch_related('mesas_secundarias', 'mesa_principal'))

        if len(uniones_activas) > 1:
            raise OperacionNoPermitida("No se pueden unir mesas que pertenecen a diferentes uniones.")

        from apps.comandas.models import Comanda
        from apps.comandas.services import ComandaService

        if len(uniones_activas) == 1:
            union_existente = uniones_activas[0]
            # Mesas que queremos agregar a la unión existente
            todas_existentes = union_existente.todas_las_mesas
            mesas_a_agregar = [m for m in mesas.values() if m not in todas_existentes]
            
            if len(todas_existentes) + len(mesas_a_agregar) > 3:
                raise OperacionNoPermitida("La union no puede exceder el maximo de 3 mesas.")
            
            # Agregar las nuevas mesas a la unión existente
            if mesas_a_agregar:
                union_existente.mesas_secundarias.add(*mesas_a_agregar)
                # Sincronizar el estado de las nuevas mesas con el de la mesa principal
                estado_principal = union_existente.mesa_principal.estado
                for m in mesas_a_agregar:
                    if m.estado != estado_principal:
                        m.estado = estado_principal
                        m.save(update_fields=['estado'])
                
                # Si hay una comanda activa para la mesa principal, asociarle las nuevas mesas
                comanda_activa = Comanda.objects.filter(
                    mesa=union_existente.mesa_principal,
                    estado__in=ComandaService.ESTADOS_ACTIVOS
                ).first()
                if comanda_activa:
                    comanda_activa.mesas_adicionales.add(*mesas_a_agregar)
            
            return union_existente

        # Si no hay ninguna unión activa previa
        comandas_activas = list(Comanda.objects.filter(
            Q(mesa__in=ids) | Q(mesas_adicionales__id__in=ids),
            estado__in=ComandaService.ESTADOS_ACTIVOS
        ).distinct())

        if len(comandas_activas) > 1:
            raise OperacionNoPermitida("No se pueden unir mesas que tienen diferentes comandas activas.")

        if len(comandas_activas) == 1:
            comanda = comandas_activas[0]
            principal_mesa = comanda.mesa
            secundarias = [m for m in mesas.values() if m.id != principal_mesa.id]
        else:
            principal_mesa = mesas[principal_id]
            secundarias = [mesas[pk] for pk in secundarias_ids]

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

        union, created = UnionMesas.objects.get_or_create(
            mesa_principal=principal_mesa,
            defaults={'activa': True, 'capacidad_personalizada': capacidad}
        )
        if not created:
            union.activa = True
            union.capacidad_personalizada = capacidad
            union.save(update_fields=['activa', 'capacidad_personalizada'])
        union.mesas_secundarias.set(secundarias)

        # Sincronizar estados de las secundarias y agregar a la comanda activa si existe
        estado_principal = principal_mesa.estado
        for m in secundarias:
            if m.estado != estado_principal:
                m.estado = estado_principal
                m.save(update_fields=['estado'])

        if len(comandas_activas) == 1:
            comandas_activas[0].mesas_adicionales.add(*secundarias)

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
