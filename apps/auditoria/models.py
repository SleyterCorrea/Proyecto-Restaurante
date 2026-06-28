from apps.usuarios.models import AuditLog as AuditLogBase


class AuditLog(AuditLogBase):
    """
    Proxy temporal del modelo de auditoria actual.

    Permite que el nuevo modulo exponga un punto de entrada propio sin mover
    aun la tabla ni alterar las migraciones existentes.
    """

    class Meta:
        proxy = True
        app_label = 'auditoria'
        verbose_name = 'Log de auditoria'
        verbose_name_plural = 'Logs de auditoria'
        ordering = ['-fecha_evento']

