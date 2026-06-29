from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('auditoria', '0003_auditlog_responsable_revision'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name='auditlog',
            name='usuario',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='logs',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name='auditlog',
            name='alerta_activa',
            field=models.BooleanField(db_index=True, default=False),
        ),
        migrations.AddField(
            model_name='auditlog',
            name='clave_alerta',
            field=models.CharField(blank=True, max_length=180, null=True),
        ),
        migrations.AddConstraint(
            model_name='auditlog',
            constraint=models.UniqueConstraint(
                condition=models.Q(alerta_activa=True, clave_alerta__isnull=False),
                fields=('clave_alerta',),
                name='audit_alerta_activa_unica',
            ),
        ),
    ]
