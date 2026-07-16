from django.db import migrations


DISCRETAS = ('UND', 'UN', 'UNI', 'U', 'PZA', 'PZ', 'BOT', 'BOTELLA')


def clasificar_unidades(apps, schema_editor):
    UnidadMedida = apps.get_model('inventario', 'UnidadMedida')
    UnidadMedida.objects.filter(abreviatura__in=DISCRETAS).update(
        tipo='DISCRETA'
    )
    UnidadMedida.objects.exclude(abreviatura__in=DISCRETAS).filter(
        tipo__isnull=True
    ).update(tipo='CONTINUA')


def desclasificar_unidades(apps, schema_editor):
    UnidadMedida = apps.get_model('inventario', 'UnidadMedida')
    UnidadMedida.objects.filter(tipo__in=('DISCRETA', 'CONTINUA')).update(
        tipo=None
    )


class Migration(migrations.Migration):
    dependencies = [
        ('inventario', '0006_insumo_control_alertas_movimiento_lote'),
    ]

    operations = [
        migrations.RunPython(clasificar_unidades, desclasificar_unidades),
    ]
