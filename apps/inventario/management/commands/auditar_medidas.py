import json

from django.core.management.base import BaseCommand, CommandError
from django.db import models
from django.db.models.functions import Lower

from apps.inventario.models import Insumo, MagnitudMedida, RecetaInsumo, UnidadMedida


class Command(BaseCommand):
    help = 'Diagnostica magnitudes, unidades, insumos y recetas sin modificar datos.'

    def add_arguments(self, parser):
        parser.add_argument('--json', action='store_true', dest='como_json')
        parser.add_argument('--fail-on-issues', action='store_true')

    def handle(self, *args, **options):
        problemas = []

        for magnitud in MagnitudMedida.objects.prefetch_related('unidades'):
            if not magnitud.activo:
                continue
            bases = list(magnitud.unidades.filter(es_base=True).values_list('id', flat=True))
            if len(bases) != 1:
                problemas.append({
                    'tipo': 'MAGNITUD_SIN_BASE_UNICA', 'id': magnitud.id,
                    'detalle': f'{magnitud.codigo}: {len(bases)} unidades base',
                })

        for unidad in UnidadMedida.objects.select_related('magnitud'):
            if unidad.factor_conversion <= 0:
                problemas.append({
                    'tipo': 'FACTOR_INVALIDO', 'id': unidad.id,
                    'detalle': unidad.simbolo,
                })

        for campo in ('nombre', 'simbolo'):
            duplicados = (
                UnidadMedida.objects.annotate(valor=Lower(campo))
                .values('valor').order_by().annotate(total=models.Count('id'))
                .filter(total__gt=1)
            )
            for duplicado in duplicados:
                problemas.append({
                    'tipo': f'UNIDAD_{campo.upper()}_DUPLICADO', 'id': None,
                    'detalle': duplicado['valor'],
                })

        afectados = set()
        for insumo in Insumo.objects.select_related('magnitud', 'unidad_medida__magnitud'):
            if insumo.magnitud_id != insumo.unidad_medida.magnitud_id:
                afectados.add(insumo.id)
                problemas.append({
                    'tipo': 'INSUMO_UNIDAD_INCOMPATIBLE', 'id': insumo.id,
                    'detalle': insumo.nombre,
                })
            if insumo.medida_requiere_revision:
                afectados.add(insumo.id)
                problemas.append({
                    'tipo': 'INSUMO_REVISION_MANUAL', 'id': insumo.id,
                    'detalle': insumo.nombre,
                })

        for receta in RecetaInsumo.objects.select_related(
            'plato', 'insumo__magnitud', 'unidad_medida__magnitud'
        ):
            if receta.insumo.magnitud_id != receta.unidad_medida.magnitud_id:
                afectados.add(receta.insumo_id)
                problemas.append({
                    'tipo': 'RECETA_UNIDAD_INCOMPATIBLE', 'id': receta.id,
                    'detalle': f'{receta.plato_id}/{receta.insumo_id}',
                })

        movimientos = Insumo.objects.filter(id__in=afectados).values(
            'id', 'nombre'
        ).annotate(total_movimientos=models.Count('movimientos'))
        resultado = {
            'total_problemas': len(problemas),
            'problemas': problemas,
            'insumos_afectados': list(movimientos),
        }
        if options['como_json']:
            self.stdout.write(json.dumps(resultado, ensure_ascii=False, indent=2))
        else:
            self.stdout.write(f"Problemas encontrados: {len(problemas)}")
            for problema in problemas:
                self.stdout.write(
                    f"- {problema['tipo']} [{problema['id']}]: {problema['detalle']}"
                )
            for insumo in resultado['insumos_afectados']:
                self.stdout.write(
                    f"  {insumo['nombre']}: {insumo['total_movimientos']} movimientos asociados"
                )
        if problemas and options['fail_on_issues']:
            raise CommandError('Existen medidas que requieren revision manual.')
