from django.db import migrations, models


def copiar_stock_a_real(apps, schema_editor):
    Insumo = apps.get_model('inventario', 'Insumo')
    for insumo in Insumo.objects.all():
        insumo.stock_real = insumo.stock_actual
        insumo.save(update_fields=['stock_real'])


class Migration(migrations.Migration):

    dependencies = [
        ('inventario', '0002_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='insumo',
            name='stock_real',
            field=models.DecimalField(decimal_places=3, default=0, max_digits=12),
        ),
        migrations.RunPython(copiar_stock_a_real, migrations.RunPython.noop),
    ]
