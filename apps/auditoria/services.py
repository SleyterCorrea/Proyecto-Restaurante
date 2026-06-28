from django.db.models import Q

from apps.usuarios.models import AuditLog as AuditLogModel


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
    ):
        ip, user_agent = AuditoriaService._extraer_metadata_request(request)
        return AuditLogModel.objects.create(
            usuario=usuario,
            accion=accion,
            entidad=entidad,
            entidad_id=entidad_id,
            detalle_anterior=detalle_anterior,
            detalle_nuevo=detalle_nuevo,
            ip=ip,
            user_agent=user_agent,
        )

    @staticmethod
    def listar_logs(search='', entidad='', accion=''):
        logs = AuditLogModel.objects.select_related('usuario').order_by('-fecha_evento')

        if search:
            logs = logs.filter(
                Q(usuario__username__icontains=search)
                | Q(detalle_nuevo__icontains=search)
                | Q(detalle_anterior__icontains=search)
            )

        if entidad:
            logs = logs.filter(entidad=entidad)

        if accion:
            logs = logs.filter(accion=accion)

        return logs

    @staticmethod
    def _extraer_metadata_request(request):
        if not request:
            return None, None

        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')

        user_agent = request.META.get('HTTP_USER_AGENT')
        return ip, user_agent

