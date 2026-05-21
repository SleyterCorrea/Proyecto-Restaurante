from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('comandas', '0004_comanda_nombre_cliente'),
    ]

    operations = [
        migrations.AddField(
            model_name='lineacomanda',
            name='tiempo_real_preparacion_seg',
            field=models.PositiveIntegerField(
                blank=True,
                help_text='Segundos reales de cocción (fecha_listo - fecha_inicio_prep). Disponible para auditoría.',
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='lineacomanda',
            name='cantidad_parcial_cocina',
            field=models.PositiveSmallIntegerField(
                blank=True,
                help_text='En cancelación parcial, cantidad que el cocinero indica que puede preparar.',
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='lineacomanda',
            name='motivo_anulacion',
            field=models.CharField(
                blank=True,
                help_text='Motivo de anulación del plato.',
                max_length=255,
                null=True,
            ),
        ),
    ]
