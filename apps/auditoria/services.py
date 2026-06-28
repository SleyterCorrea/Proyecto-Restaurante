from django.db.models import Q

from .models import AuditLog


class AuditoriaService:
    @staticmethod
    def registrar(
        usuario,
        accion,
        entidad,
        entidad_id,
        detalle_anterior=None,
        detalle_nuevo=None,
        request=None,
        rol=None,
        modulo=None,
        codigo_evento=None,
        severidad=AuditLog.Severidad.INFO,
        descripcion='',
        motivo=None,
        impacto_economico_estimado=None,
    ):
        metadata = AuditoriaService._extraer_metadata_request(request)
        nombre_rol = rol or getattr(getattr(usuario, 'rol', None), 'nombre', None)

        return AuditLog.objects.create(
            usuario=usuario,
            rol=nombre_rol,
            modulo=modulo or entidad,
            codigo_evento=codigo_evento or accion,
            severidad=severidad,
            accion=accion,
            entidad=entidad,
            entidad_id=entidad_id,
            descripcion=descripcion,
            motivo=motivo,
            detalle_anterior=detalle_anterior,
            detalle_nuevo=detalle_nuevo,
            impacto_economico_estimado=impacto_economico_estimado,
            **metadata,
        )

    @staticmethod
    def listar_logs(
        search='',
        entidad='',
        accion='',
        modulo='',
        severidad='',
        estado_revision='',
    ):
        logs = AuditLog.objects.select_related('usuario').order_by('-fecha_evento')

        if search:
            logs = logs.filter(
                Q(usuario__username__icontains=search)
                | Q(codigo_evento__icontains=search)
                | Q(descripcion__icontains=search)
                | Q(motivo__icontains=search)
                | Q(detalle_nuevo__icontains=search)
                | Q(detalle_anterior__icontains=search)
            )

        if entidad:
            logs = logs.filter(entidad=entidad)

        if accion:
            logs = logs.filter(Q(accion=accion) | Q(codigo_evento=accion))

        if modulo:
            logs = logs.filter(modulo=modulo)

        if severidad:
            logs = logs.filter(severidad=severidad)

        if estado_revision:
            logs = logs.filter(estado_revision=estado_revision)

        return logs

    @staticmethod
    def _extraer_metadata_request(request):
        if not request:
            return {
                'ip': None,
                'user_agent': None,
                'ruta': None,
                'metodo_http': None,
            }

        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')

        return {
            'ip': ip,
            'user_agent': request.META.get('HTTP_USER_AGENT'),
            'ruta': request.path[:255],
            'metodo_http': request.method[:10],
        }
