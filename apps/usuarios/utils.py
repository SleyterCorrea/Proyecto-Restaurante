from .models import AuditLog

def log_auditoria(usuario, accion, entidad, entidad_id, detalle_anterior=None, detalle_nuevo=None, request=None):
    """
    Registra una acción en el log de auditoría.
    """
    ip = None
    user_agent = None
    
    if request:
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        user_agent = request.META.get('HTTP_USER_AGENT')

    AuditLog.objects.create(
        usuario=usuario,
        accion=accion,
        entidad=entidad,
        entidad_id=entidad_id,
        detalle_anterior=detalle_anterior,
        detalle_nuevo=detalle_nuevo,
        ip=ip,
        user_agent=user_agent
    )
