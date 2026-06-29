import csv
from datetime import datetime, time, timedelta

from django.http import HttpResponse
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from .constants import (
    ACCIONES_AUDITABLES,
    ACCIONES_CON_MOTIVO_OBLIGATORIO,
)
from .models import AuditLog


class AuditoriaService:
    ACCIONES_PERMITIDAS = ACCIONES_AUDITABLES
    ACCIONES_CON_MOTIVO_OBLIGATORIO = ACCIONES_CON_MOTIVO_OBLIGATORIO

    CLAVES_CONTEXTO_PERMITIDAS = frozenset({
        'rol',
        'impacto_economico_estimado',
        'ip',
        'user_agent',
        'ruta',
        'metodo_http',
    })

    @classmethod
    def registrar(
        cls,
        usuario,
        accion,
        modulo,
        entidad,
        entidad_id,
        severidad,
        estado_resultado,
        descripcion,
        motivo=None,
        valores_anteriores=None,
        valores_nuevos=None,
        request=None,
        datos_contextuales=None,
        deduplicar_alerta=False,
        clave_alerta=None,
        deduplicar_durante_minutos=None,
    ):
        """Registra un evento critico luego de validar el contrato oficial."""
        accion = cls._validar_accion(accion)
        motivo = cls._validar_motivo(accion, motivo)
        cls._validar_opcion(
            'severidad',
            severidad,
            AuditLog.Severidad.values,
        )
        cls._validar_opcion(
            'estado_resultado',
            estado_resultado,
            AuditLog.EstadoResultado.values,
        )
        cls._validar_requerido('modulo', modulo)
        cls._validar_requerido('entidad', entidad)
        if entidad_id is None:
            raise ValidationError({'entidad_id': 'La entidad afectada requiere un ID.'})

        contexto = cls._validar_contexto(datos_contextuales)
        metadata = cls._resolver_metadata(request, contexto)
        rol = contexto.get('rol') or getattr(
            getattr(usuario, 'rol', None),
            'nombre',
            None,
        )

        clave_alerta = cls._normalizar_clave_alerta(
            accion,
            entidad,
            entidad_id,
            deduplicar_alerta,
            clave_alerta,
        )
        existente = cls._buscar_duplicado(
            accion=accion,
            entidad=entidad,
            entidad_id=entidad_id,
            clave_alerta=clave_alerta,
            deduplicar_durante_minutos=deduplicar_durante_minutos,
        )
        if existente:
            return existente

        datos_registro = dict(
            usuario=usuario,
            accion=accion,
            modulo=str(modulo).strip(),
            entidad=str(entidad).strip(),
            entidad_id=entidad_id,
            severidad=severidad,
            estado_resultado=estado_resultado,
            descripcion=descripcion or '',
            motivo=motivo,
            valores_anteriores=valores_anteriores,
            valores_nuevos=valores_nuevos,
            rol=rol,
            impacto_economico_estimado=contexto.get(
                'impacto_economico_estimado'
            ),
            metadata=metadata,
            alerta_activa=bool(deduplicar_alerta),
            clave_alerta=clave_alerta,
        )
        try:
            with transaction.atomic():
                return cls._crear_registro(**datos_registro)
        except IntegrityError:
            if not clave_alerta:
                raise
            return AuditLog.objects.get(
                clave_alerta=clave_alerta,
                alerta_activa=True,
            )

    @staticmethod
    def _crear_registro(
        *,
        usuario,
        accion,
        modulo,
        entidad,
        entidad_id,
        severidad,
        estado_resultado,
        descripcion,
        motivo,
        valores_anteriores,
        valores_nuevos,
        rol,
        impacto_economico_estimado,
        metadata,
        alerta_activa,
        clave_alerta,
    ):
        return AuditLog.objects.create(
            usuario=usuario,
            rol=rol,
            modulo=modulo,
            codigo_evento=accion,
            severidad=severidad,
            estado_resultado=estado_resultado,
            accion=accion,
            entidad=entidad,
            entidad_id=entidad_id,
            descripcion=descripcion,
            motivo=motivo,
            detalle_anterior=valores_anteriores,
            detalle_nuevo=valores_nuevos,
            impacto_economico_estimado=impacto_economico_estimado,
            alerta_activa=alerta_activa,
            clave_alerta=clave_alerta,
            **metadata,
        )

    @staticmethod
    def _normalizar_clave_alerta(
        accion,
        entidad,
        entidad_id,
        deduplicar_alerta,
        clave_alerta,
    ):
        if not deduplicar_alerta:
            return None
        clave = clave_alerta or f'{accion}:{entidad}:{entidad_id}'
        return str(clave).strip()[:180]

    @staticmethod
    def _buscar_duplicado(
        *,
        accion,
        entidad,
        entidad_id,
        clave_alerta,
        deduplicar_durante_minutos,
    ):
        if clave_alerta:
            return AuditLog.objects.filter(
                clave_alerta=clave_alerta,
                alerta_activa=True,
            ).first()
        if deduplicar_durante_minutos:
            desde = timezone.now() - timedelta(
                minutes=deduplicar_durante_minutos
            )
            return AuditLog.objects.filter(
                accion=accion,
                entidad=entidad,
                entidad_id=entidad_id,
                fecha_evento__gte=desde,
            ).first()
        return None

    @staticmethod
    def resolver_alerta(*, accion=None, entidad=None, entidad_id=None, clave_alerta=None):
        """Marca una condicion como resuelta para permitir una alerta futura."""
        filtros = {'alerta_activa': True}
        if clave_alerta:
            filtros['clave_alerta'] = clave_alerta
        else:
            if accion:
                filtros['accion'] = accion
            if entidad:
                filtros['entidad'] = entidad
            if entidad_id is not None:
                filtros['entidad_id'] = entidad_id
        return AuditLog.objects.filter(**filtros).update(alerta_activa=False)

    @classmethod
    def _validar_accion(cls, accion):
        accion_normalizada = str(accion or '').strip()
        if accion_normalizada not in cls.ACCIONES_PERMITIDAS:
            raise ValidationError({
                'accion': f'Accion de auditoria no permitida: {accion_normalizada}.'
            })
        return accion_normalizada

    @classmethod
    def _validar_motivo(cls, accion, motivo):
        motivo_normalizado = motivo.strip() if isinstance(motivo, str) else motivo
        if accion in cls.ACCIONES_CON_MOTIVO_OBLIGATORIO and not motivo_normalizado:
            raise ValidationError({
                'motivo': f'El motivo es obligatorio para la accion {accion}.'
            })
        return motivo_normalizado

    @staticmethod
    def _validar_opcion(campo, valor, permitidos):
        if valor not in permitidos:
            raise ValidationError({
                campo: f'Valor no permitido: {valor}.'
            })

    @staticmethod
    def _validar_requerido(campo, valor):
        if not str(valor or '').strip():
            raise ValidationError({campo: 'Este campo es obligatorio.'})

    @classmethod
    def _validar_contexto(cls, datos_contextuales):
        if datos_contextuales is None:
            return {}
        if not isinstance(datos_contextuales, dict):
            raise ValidationError({
                'datos_contextuales': 'Debe ser un diccionario.'
            })

        desconocidas = set(datos_contextuales) - cls.CLAVES_CONTEXTO_PERMITIDAS
        if desconocidas:
            raise ValidationError({
                'datos_contextuales': (
                    'Claves no permitidas: ' + ', '.join(sorted(desconocidas))
                )
            })
        return datos_contextuales.copy()

    @classmethod
    def _resolver_metadata(cls, request, contexto):
        metadata = {
            'ip': contexto.get('ip'),
            'user_agent': contexto.get('user_agent'),
            'ruta': contexto.get('ruta'),
            'metodo_http': contexto.get('metodo_http'),
        }
        if request:
            metadata_request = cls._extraer_metadata_request(request)
            metadata.update({
                clave: valor
                for clave, valor in metadata_request.items()
                if valor is not None
            })

        if metadata['user_agent']:
            metadata['user_agent'] = str(metadata['user_agent'])[:255]
        if metadata['ruta']:
            metadata['ruta'] = str(metadata['ruta'])[:255]
        if metadata['metodo_http']:
            metadata['metodo_http'] = str(metadata['metodo_http']).upper()[:10]
        return metadata

    @staticmethod
    def _extraer_metadata_request(request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR')

        return {
            'ip': ip,
            'user_agent': request.META.get('HTTP_USER_AGENT'),
            'ruta': getattr(request, 'path', None),
            'metodo_http': getattr(request, 'method', None),
        }

    @classmethod
    def listar_logs(
        cls,
        search='',
        fecha_desde='',
        fecha_hasta='',
        turno_caja='',
        usuario_id='',
        rol='',
        entidad='',
        entidad_id='',
        accion='',
        modulo='',
        severidad='',
        motivo_obligatorio='',
        estado_resultado='',
        estado_revision='',
        responsable_revision_id='',
        mesa='',
        plato='',
        insumo='',
    ):
        logs = AuditLog.objects.select_related(
            'usuario',
            'responsable_revision',
        ).order_by('-fecha_evento')

        if search:
            logs = logs.filter(
                Q(usuario__username__icontains=search)
                | Q(rol__icontains=search)
                | Q(codigo_evento__icontains=search)
                | Q(entidad__icontains=search)
                | Q(descripcion__icontains=search)
                | Q(motivo__icontains=search)
                | Q(detalle_nuevo__icontains=search)
                | Q(detalle_anterior__icontains=search)
            )

        fecha_desde_dt = AuditoriaService._parse_fecha(fecha_desde, end_of_day=False)
        if fecha_desde_dt:
            logs = logs.filter(fecha_evento__gte=fecha_desde_dt)

        fecha_hasta_dt = AuditoriaService._parse_fecha(fecha_hasta, end_of_day=True)
        if fecha_hasta_dt:
            logs = logs.filter(fecha_evento__lte=fecha_hasta_dt)

        if turno_caja:
            logs = logs.filter(
                Q(entidad='CAJA_TURNO', entidad_id=turno_caja)
                | Q(descripcion__icontains=turno_caja)
                | Q(detalle_nuevo__icontains=turno_caja)
                | Q(detalle_anterior__icontains=turno_caja)
            )

        if usuario_id:
            logs = logs.filter(usuario_id=usuario_id)

        if rol:
            logs = logs.filter(rol=rol)

        if entidad:
            logs = logs.filter(entidad=entidad)

        if entidad_id:
            logs = logs.filter(entidad_id=entidad_id)

        if accion:
            logs = logs.filter(Q(accion=accion) | Q(codigo_evento=accion))

        if modulo:
            logs = logs.filter(modulo=modulo)

        if severidad:
            logs = logs.filter(severidad=severidad)

        if motivo_obligatorio == 'true':
            logs = logs.exclude(motivo__isnull=True).exclude(motivo__exact='')
        elif motivo_obligatorio == 'false':
            logs = logs.filter(Q(motivo__isnull=True) | Q(motivo__exact=''))

        if estado_resultado:
            logs = logs.filter(estado_resultado=estado_resultado)

        if estado_revision:
            logs = logs.filter(estado_revision=estado_revision)

        if responsable_revision_id:
            logs = logs.filter(responsable_revision_id=responsable_revision_id)

        if mesa:
            logs = logs.filter(cls._build_entidad_relacionada_q('MESA', mesa))

        if plato:
            logs = logs.filter(cls._build_entidad_relacionada_q('PLATO', plato))

        if insumo:
            logs = logs.filter(cls._build_entidad_relacionada_q('INSUMO', insumo))

        return logs

    @staticmethod
    def obtener_log(log_id):
        return AuditLog.objects.select_related(
            'usuario',
            'responsable_revision',
        ).get(pk=log_id)

    @classmethod
    def actualizar_estado_revision(cls, log_id, nuevo_estado, responsable):
        """Cambia el estado de revisión de un evento auditado.

        Solo se aceptan los estados ya definidos en el modelo. Se registra al
        administrador como responsable salvo que el evento vuelva a PENDIENTE.
        """
        estado = str(nuevo_estado or '').strip().upper()
        if estado not in AuditLog.EstadoRevision.values:
            raise ValidationError({
                'estado_revision': f'Estado de revision no permitido: {estado or "vacio"}.'
            })

        log = AuditLog.objects.get(pk=log_id)
        log.estado_revision = estado
        if estado == AuditLog.EstadoRevision.PENDIENTE:
            log.responsable_revision = None
        else:
            log.responsable_revision = responsable
        log.save(update_fields=[
            'estado_revision',
            'responsable_revision',
            'updated_at',
        ])
        return cls.obtener_log(log.id)

    @staticmethod
    def obtener_opciones_filtro():
        base = AuditLog.objects.select_related('usuario', 'responsable_revision')
        return {
            'usuarios': list(
                base.exclude(usuario__isnull=True)
                .values('usuario_id', 'usuario__username')
                .distinct()
                .order_by('usuario__username')
            ),
            'roles': list(
                base.exclude(rol__exact='')
                .exclude(rol__isnull=True)
                .values_list('rol', flat=True)
                .distinct()
                .order_by('rol')
            ),
            'modulos': list(
                base.exclude(modulo__exact='')
                .values_list('modulo', flat=True)
                .distinct()
                .order_by('modulo')
            ),
            'severidades': list(AuditLog.Severidad.values),
            'tipos_evento': list(
                base.exclude(codigo_evento__exact='')
                .values_list('codigo_evento', flat=True)
                .distinct()
                .order_by('codigo_evento')
            ),
            'entidades': list(
                base.exclude(entidad__exact='')
                .values_list('entidad', flat=True)
                .distinct()
                .order_by('entidad')
            ),
            'estados_revision': list(AuditLog.EstadoRevision.values),
            'responsables_revision': list(
                base.exclude(responsable_revision__isnull=True)
                .values(
                    'responsable_revision_id',
                    'responsable_revision__username',
                )
                .distinct()
                .order_by('responsable_revision__username')
            ),
        }

    @classmethod
    def exportar_logs_csv(cls, logs):
        response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
        response['Content-Disposition'] = 'attachment; filename="auditoria_logs.csv"'
        writer = csv.writer(response)
        writer.writerow([
            'Fecha',
            'Usuario',
            'Rol',
            'Modulo',
            'Evento',
            'Severidad',
            'Resultado',
            'Entidad',
            'Entidad ID',
            'Descripcion',
            'Motivo',
            'Estado revision',
            'Responsable revision',
            'IP',
            'Ruta',
            'Metodo',
        ])
        for log in logs:
            writer.writerow([
                timezone.localtime(log.fecha_evento).strftime('%Y-%m-%d %H:%M:%S'),
                getattr(log.usuario, 'username', ''),
                log.rol,
                log.modulo,
                log.codigo_evento or log.accion,
                log.severidad,
                log.estado_resultado,
                log.entidad,
                log.entidad_id,
                log.descripcion,
                log.motivo or '',
                log.estado_revision,
                getattr(log.responsable_revision, 'username', ''),
                log.ip or '',
                log.ruta or '',
                log.metodo_http or '',
            ])
        return response

    @staticmethod
    def _parse_fecha(valor, *, end_of_day):
        if not valor:
            return None
        try:
            fecha = datetime.strptime(valor, '%Y-%m-%d').date()
        except ValueError:
            raise ValidationError({'fecha': f'Fecha invalida: {valor}.'})
        hora = time.max if end_of_day else time.min
        return timezone.make_aware(datetime.combine(fecha, hora))

    @staticmethod
    def _build_entidad_relacionada_q(entidad, valor):
        filtros = (
            Q(descripcion__icontains=valor)
            | Q(detalle_nuevo__icontains=valor)
            | Q(detalle_anterior__icontains=valor)
        )
        if str(valor).isdigit():
            filtros |= Q(entidad=entidad, entidad_id=int(valor))
        return filtros
