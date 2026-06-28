from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('auditoria', '0002_auditlog_estado_resultado'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='auditlog',
            name='responsable_revision',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.PROTECT,
                related_name='audit_logs_revisados',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
