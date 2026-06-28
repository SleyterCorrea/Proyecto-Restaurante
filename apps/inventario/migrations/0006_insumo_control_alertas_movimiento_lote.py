from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inventario', '0005_ordencompra_ordencompraitem_insumo_categoria_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='insumo',
            name='agotado_desde',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='insumo',
            name='es_critico',
            field=models.BooleanField(db_index=True, default=False),
        ),
        migrations.AddField(
            model_name='insumo',
            name='stock_bajo_desde',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='movimientoinventario',
            name='lote',
            field=models.CharField(blank=True, db_index=True, max_length=80, null=True),
        ),
    ]
