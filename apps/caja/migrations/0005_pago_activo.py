from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('caja', '0004_add_punto_caja_arqueo_perdida'),
    ]

    operations = [
        migrations.AddField(
            model_name='pago',
            name='activo',
            field=models.BooleanField(db_index=True, default=True),
        ),
    ]
