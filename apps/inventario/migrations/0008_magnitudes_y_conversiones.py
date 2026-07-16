from decimal import Decimal

import django.db.models.deletion
from django.db import migrations, models
from django.db.models.functions import Lower


MAGNITUDES = {
    'MASA': 'Masa',
    'VOLUMEN': 'Volumen',
    'UNIDAD': 'Unidad',
    'SIN_CLASIFICAR': 'Sin clasificar',
}

UNIDADES_CONOCIDAS = {
    'g': ('MASA', Decimal('1'), True, 'CONTINUA'),
    'gr': ('MASA', Decimal('1'), True, 'CONTINUA'),
    'kg': ('MASA', Decimal('1000'), False, 'CONTINUA'),
    'ml': ('VOLUMEN', Decimal('1'), True, 'CONTINUA'),
    'l': ('VOLUMEN', Decimal('1000'), False, 'CONTINUA'),
    'lt': ('VOLUMEN', Decimal('1000'), False, 'CONTINUA'),
    'und': ('UNIDAD', Decimal('1'), True, 'DISCRETA'),
    'un': ('UNIDAD', Decimal('1'), True, 'DISCRETA'),
    'u': ('UNIDAD', Decimal('1'), True, 'DISCRETA'),
    'doc': ('UNIDAD', Decimal('12'), False, 'DISCRETA'),
    'bot': ('UNIDAD', Decimal('1'), False, 'DISCRETA'),
}


def _normalizar_duplicados(UnidadMedida, Insumo):
    vistos_simbolo = {}
    vistos_nombre = {}
    for unidad in UnidadMedida.objects.order_by('id'):
        simbolo = (unidad.simbolo or '').strip().lower()
        nombre = ' '.join((unidad.nombre or '').split())
        requiere_revision = False

        if simbolo in vistos_simbolo:
            simbolo = f'{simbolo or "unidad"}-{unidad.id}'
            unidad.activo = False
            requiere_revision = True
        else:
            vistos_simbolo[simbolo] = unidad.id

        clave_nombre = nombre.casefold()
        if clave_nombre in vistos_nombre:
            nombre = f'{nombre} (revisar {unidad.id})'
            unidad.activo = False
            requiere_revision = True
        else:
            vistos_nombre[clave_nombre] = unidad.id

        unidad.simbolo = simbolo
        unidad.nombre = nombre
        unidad.save(update_fields=['simbolo', 'nombre', 'activo'])
        if requiere_revision:
            Insumo.objects.filter(unidad_medida_id=unidad.id).update(
                medida_requiere_revision=True
            )


def preparar_magnitudes(apps, schema_editor):
    MagnitudMedida = apps.get_model('inventario', 'MagnitudMedida')
    UnidadMedida = apps.get_model('inventario', 'UnidadMedida')
    Insumo = apps.get_model('inventario', 'Insumo')
    RecetaInsumo = apps.get_model('inventario', 'RecetaInsumo')

    magnitudes = {}
    for codigo, nombre in MAGNITUDES.items():
        magnitud, _ = MagnitudMedida.objects.get_or_create(
            codigo=codigo,
            defaults={'nombre': nombre, 'activo': codigo != 'SIN_CLASIFICAR'},
        )
        magnitudes[codigo] = magnitud

    _normalizar_duplicados(UnidadMedida, Insumo)

    for unidad in UnidadMedida.objects.order_by('id'):
        simbolo = (unidad.simbolo or '').strip().lower()
        clave = simbolo.split('-', 1)[0]
        configuracion = UNIDADES_CONOCIDAS.get(clave)
        if configuracion:
            codigo, factor, es_base, tipo = configuracion
        else:
            codigo, factor, es_base, tipo = (
                'SIN_CLASIFICAR', Decimal('1'), False, unidad.tipo or 'CONTINUA'
            )
            Insumo.objects.filter(unidad_medida_id=unidad.id).update(
                medida_requiere_revision=True
            )

        # BOT representa conteo de presentaciones, pero requiere confirmación
        # manual porque el nombre también puede expresar capacidad volumétrica.
        if clave == 'bot':
            Insumo.objects.filter(unidad_medida_id=unidad.id).update(
                medida_requiere_revision=True
            )

        unidad.magnitud_id = magnitudes[codigo].id
        unidad.factor_conversion = factor
        unidad.es_base = es_base
        unidad.tipo = tipo
        unidad.save(update_fields=[
            'magnitud_id', 'factor_conversion', 'es_base', 'tipo'
        ])

    unidades_minimas = (
        ('Gramo', 'g', 'MASA', Decimal('1'), True, 'CONTINUA'),
        ('Kilogramo', 'kg', 'MASA', Decimal('1000'), False, 'CONTINUA'),
        ('Mililitro', 'ml', 'VOLUMEN', Decimal('1'), True, 'CONTINUA'),
        ('Litro', 'l', 'VOLUMEN', Decimal('1000'), False, 'CONTINUA'),
        ('Unidad', 'und', 'UNIDAD', Decimal('1'), True, 'DISCRETA'),
        ('Docena', 'doc', 'UNIDAD', Decimal('12'), False, 'DISCRETA'),
    )
    for nombre, simbolo, codigo, factor, es_base, tipo in unidades_minimas:
        unidad = UnidadMedida.objects.filter(simbolo__iexact=simbolo).first()
        if unidad is None:
            nombre_disponible = nombre
            if UnidadMedida.objects.filter(nombre__iexact=nombre).exists():
                nombre_disponible = f'{nombre} ({simbolo})'
            UnidadMedida.objects.create(
                nombre=nombre_disponible,
                simbolo=simbolo,
                magnitud_id=magnitudes[codigo].id,
                factor_conversion=factor,
                es_base=es_base,
                tipo=tipo,
                activo=True,
            )
        else:
            unidad.magnitud_id = magnitudes[codigo].id
            unidad.factor_conversion = factor
            unidad.es_base = es_base
            unidad.tipo = tipo
            unidad.save(update_fields=[
                'magnitud_id', 'factor_conversion', 'es_base', 'tipo'
            ])

    # Los alias historicos no pueden quedar todos como referencia. Se conserva
    # una unica unidad base explicita por magnitud.
    for codigo, simbolo_base in (('MASA', 'g'), ('VOLUMEN', 'ml'), ('UNIDAD', 'und')):
        UnidadMedida.objects.filter(magnitud_id=magnitudes[codigo].id).update(
            es_base=False
        )
        UnidadMedida.objects.filter(simbolo__iexact=simbolo_base).update(
            es_base=True, factor_conversion=Decimal('1')
        )

    for insumo in Insumo.objects.select_related('unidad_medida'):
        insumo.magnitud_id = insumo.unidad_medida.magnitud_id
        insumo.save(update_fields=['magnitud_id'])

    for receta in RecetaInsumo.objects.select_related('insumo'):
        receta.unidad_medida_id = receta.insumo.unidad_medida_id
        receta.save(update_fields=['unidad_medida_id'])


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ('inventario', '0007_clasificar_unidades_medida'),
    ]

    operations = [
        migrations.CreateModel(
            name='MagnitudMedida',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('codigo', models.SlugField(max_length=30, unique=True)),
                ('nombre', models.CharField(max_length=60, unique=True)),
                ('activo', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Magnitud de medida',
                'verbose_name_plural': 'Magnitudes de medida',
                'db_table': 'magnitud_medida',
                'ordering': ('nombre',),
            },
        ),
        migrations.RenameField(
            model_name='unidadmedida', old_name='abreviatura', new_name='simbolo'
        ),
        migrations.AlterModelOptions(
            name='unidadmedida',
            options={
                'ordering': ('magnitud__nombre', 'factor_conversion', 'nombre'),
                'verbose_name': 'Unidad de Medida',
            },
        ),
        migrations.AddField(
            model_name='unidadmedida', name='es_base',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='unidadmedida', name='factor_conversion',
            field=models.DecimalField(decimal_places=8, default=Decimal('1'), help_text='Cantidad de unidades base equivalentes a una unidad de medida.', max_digits=18),
        ),
        migrations.AddField(
            model_name='unidadmedida', name='magnitud',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, related_name='unidades', to='inventario.magnitudmedida'),
        ),
        migrations.AddField(
            model_name='insumo', name='magnitud',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, related_name='insumos', to='inventario.magnitudmedida'),
        ),
        migrations.AddField(
            model_name='insumo', name='medida_requiere_revision',
            field=models.BooleanField(db_index=True, default=False),
        ),
        migrations.AddField(
            model_name='recetainsumo', name='unidad_medida',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, related_name='recetas', to='inventario.unidadmedida'),
        ),
        migrations.AlterField(model_name='insumo', name='stock_actual', field=models.DecimalField(decimal_places=6, default=0, max_digits=16)),
        migrations.AlterField(model_name='insumo', name='stock_minimo', field=models.DecimalField(decimal_places=6, default=0, max_digits=16)),
        migrations.AlterField(model_name='insumo', name='stock_real', field=models.DecimalField(db_index=True, decimal_places=6, default=0, max_digits=16)),
        migrations.AlterField(model_name='movimientoinventario', name='cantidad', field=models.DecimalField(decimal_places=6, max_digits=16)),
        migrations.AlterField(model_name='movimientoinventario', name='stock_anterior', field=models.DecimalField(decimal_places=6, max_digits=16)),
        migrations.AlterField(model_name='movimientoinventario', name='stock_nuevo', field=models.DecimalField(decimal_places=6, max_digits=16)),
        migrations.AlterField(model_name='ordencompraitem', name='cantidad_recibida', field=models.DecimalField(decimal_places=6, default=0, max_digits=16)),
        migrations.AlterField(model_name='ordencompraitem', name='cantidad_solicitada', field=models.DecimalField(decimal_places=6, max_digits=16)),
        migrations.AlterField(model_name='recetainsumo', name='cantidad_por_porcion', field=models.DecimalField(decimal_places=6, max_digits=16)),
        migrations.RunPython(preparar_magnitudes, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='unidadmedida', name='magnitud',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='unidades', to='inventario.magnitudmedida'),
        ),
        migrations.AlterField(
            model_name='insumo', name='magnitud',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='insumos', to='inventario.magnitudmedida'),
        ),
        migrations.AlterField(
            model_name='recetainsumo', name='unidad_medida',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='recetas', to='inventario.unidadmedida'),
        ),
        migrations.AddConstraint(
            model_name='magnitudmedida',
            constraint=models.UniqueConstraint(Lower('nombre'), name='magnitud_nombre_ci_uniq'),
        ),
        migrations.AddConstraint(
            model_name='unidadmedida',
            constraint=models.UniqueConstraint(Lower('nombre'), name='unidad_nombre_ci_uniq'),
        ),
        migrations.AddConstraint(
            model_name='unidadmedida',
            constraint=models.UniqueConstraint(Lower('simbolo'), name='unidad_simbolo_ci_uniq'),
        ),
        migrations.AddConstraint(
            model_name='unidadmedida',
            constraint=models.UniqueConstraint(condition=models.Q(es_base=True), fields=('magnitud',), name='unidad_base_magnitud_uniq'),
        ),
        migrations.AddConstraint(
            model_name='unidadmedida',
            constraint=models.CheckConstraint(check=models.Q(factor_conversion__gt=0), name='unidad_factor_positivo_ck'),
        ),
    ]
