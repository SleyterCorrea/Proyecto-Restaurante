from apps.auditoria.models import AuditLog
from apps.auditoria.services import AuditoriaService


def log_auditoria(
    usuario,
    accion,
    entidad,
    entidad_id,
    detalle_anterior=None,
    detalle_nuevo=None,
    request=None,
    ip=None,
    valores_anteriores=None,
    valores_nuevos=None,
    modulo=None,
    severidad=AuditLog.Severidad.INFO,
    estado_resultado=AuditLog.EstadoResultado.EXITOSO,
    descripcion='',
    motivo=None,
    datos_contextuales=None,
):
    """Adaptador temporal de la firma historica al servicio oficial."""
    if accion not in AuditoriaService.ACCIONES_PERMITIDAS:
        return None

    contexto = dict(datos_contextuales or {})
    if ip is not None:
        contexto['ip'] = ip

    anteriores = (
        valores_anteriores
        if valores_anteriores is not None
        else detalle_anterior
    )
    nuevos = valores_nuevos if valores_nuevos is not None else detalle_nuevo

    return AuditoriaService.registrar(
        usuario=usuario,
        accion=accion,
        modulo=modulo or entidad,
        entidad=entidad,
        entidad_id=entidad_id,
        severidad=severidad,
        estado_resultado=estado_resultado,
        descripcion=descripcion or accion.replace('_', ' ').capitalize(),
        motivo=motivo,
        valores_anteriores=anteriores,
        valores_nuevos=nuevos,
        request=request,
        datos_contextuales=contexto,
    )
