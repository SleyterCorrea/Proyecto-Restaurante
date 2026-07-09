from django.db import migrations


def desactivar_zval(apps, schema_editor):
    Zona = apps.get_model('mesas', 'Zona')
    Zona.objects.filter(nombre__iexact='ZVAL').update(activo=False)


def revertir(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('mesas', '0004_unionmesas_capacidad_personalizada'),
    ]

    operations = [
        migrations.RunPython(desactivar_zval, revertir),
    ]
