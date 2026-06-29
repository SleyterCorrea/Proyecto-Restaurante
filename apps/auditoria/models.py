from django.conf import settings
from django.db import models


class AuditLog(models.Model):
    class Severidad(models.TextChoices):
        INFO = 'INFO', 'Informativa'
        ADVERTENCIA = 'ADVERTENCIA', 'Advertencia'
        CRITICA = 'CRITICA', 'Critica'

    class EstadoRevision(models.TextChoices):
        PENDIENTE = 'PENDIENTE', 'Pendiente'
        EN_REVISION = 'EN_REVISION', 'En revision'
        REVISADO = 'REVISADO', 'Revisado'
        DESCARTADO = 'DESCARTADO', 'Descartado'

    class EstadoResultado(models.TextChoices):
        EXITOSO = 'EXITOSO', 'Exitoso'
        FALLIDO = 'FALLIDO', 'Fallido'
        DENEGADO = 'DENEGADO', 'Denegado'

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='logs',
        null=True,
        blank=True,
    )
    rol = models.CharField(max_length=50, null=True, blank=True)
    modulo = models.CharField(max_length=50, blank=True, default='')
    codigo_evento = models.CharField(max_length=100, blank=True, default='')
    severidad = models.CharField(
        max_length=20,
        choices=Severidad.choices,
        default=Severidad.INFO,
    )
    estado_resultado = models.CharField(
        max_length=20,
        choices=EstadoResultado.choices,
        default=EstadoResultado.EXITOSO,
    )

    # Campo legado: las llamadas actuales aun expresan el evento como accion.
    accion = models.CharField(max_length=50)
    entidad = models.CharField(max_length=50)
    entidad_id = models.BigIntegerField()
    descripcion = models.TextField(blank=True, default='')
    motivo = models.TextField(null=True, blank=True)
    detalle_anterior = models.JSONField(null=True, blank=True)
    detalle_nuevo = models.JSONField(null=True, blank=True)
    impacto_economico_estimado = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
    )

    ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=255, null=True, blank=True)
    ruta = models.CharField(max_length=255, null=True, blank=True)
    metodo_http = models.CharField(max_length=10, null=True, blank=True)
    fecha_evento = models.DateTimeField(auto_now_add=True)
    estado_revision = models.CharField(
        max_length=20,
        choices=EstadoRevision.choices,
        default=EstadoRevision.PENDIENTE,
    )
    responsable_revision = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='audit_logs_revisados',
        null=True,
        blank=True,
    )
    alerta_activa = models.BooleanField(default=False, db_index=True)
    clave_alerta = models.CharField(max_length=180, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'audit_log'
        verbose_name = 'Log de auditoria'
        verbose_name_plural = 'Logs de auditoria'
        ordering = ['-fecha_evento']
        constraints = [
            models.UniqueConstraint(
                fields=['clave_alerta'],
                condition=models.Q(alerta_activa=True, clave_alerta__isnull=False),
                name='audit_alerta_activa_unica',
            ),
        ]

    def __str__(self):
        evento = self.codigo_evento or self.accion
        return f'{evento} - {self.entidad} #{self.entidad_id}'
