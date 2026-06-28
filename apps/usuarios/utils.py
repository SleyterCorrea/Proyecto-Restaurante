from apps.auditoria.services import AuditoriaService


def log_auditoria(
    usuario,
    accion,
    entidad,
    entidad_id,
    detalle_anterior=None,
    detalle_nuevo=None,
    request=None,
):
    """
    Mantiene el punto de entrada historico mientras la auditoria migra
    progresivamente al nuevo modulo propietario.
    """

    return AuditoriaService._registrar_legacy(
        usuario=usuario,
        accion=accion,
        entidad=entidad,
        entidad_id=entidad_id,
        detalle_anterior=detalle_anterior,
        detalle_nuevo=detalle_nuevo,
        request=request,
    )
