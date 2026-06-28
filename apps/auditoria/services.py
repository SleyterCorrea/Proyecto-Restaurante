from django.core.exceptions import ValidationError
from django.db.models import Q

from .models import AuditLog


class AuditoriaService:
    ACCIONES_PERMITIDAS = frozenset({
        'COMANDA_PLATO_ANULADO',
        'COMANDA_PLATO_ANULADO_POST_COCINA',
        'COMANDA_ANULADA',
        'COMANDA_ANULADA_CON_PRODUCCION',
        'CAJA_TURNO_ABIERTO',
        'CAJA_TURNO_CERRADO',
        'CAJA_DESCUADRE_DETECTADO',
        'CAJA_CIERRE_FORZADO',
        'CAJA_TURNO_REABIERTO',
        'PAGO_METODO_MODIFICADO',
        'PAGO_ANULADO',
        'PAGO_SOFT_DELETE',
        'INVENTARIO_INSUMO_AGOTADO_SIN_REPOSICION',
        'INVENTARIO_STOCK_BAJO_PERSISTENTE',
        'INVENTARIO_MERMA_ELEVADA',
        'INVENTARIO_EGRESO_INCOHERENTE',
        'INVENTARIO_AJUSTE_MANUAL_ELEVADO',
        'INVENTARIO_AJUSTES_REPETIDOS',
        'INVENTARIO_LOTE_REPETIDO',
        'INVENTARIO_COSTO_UNITARIO_VARIACION_ALTA',
        'INVENTARIO_STOCK_INSUFICIENTE_REITERADO',
        'RECETA_MODIFICADA',
        'RECETA_INSUMO_ELIMINADO',
        'PLATO_DESHABILITADO_STOCK',
        'PLATO_REACTIVADO_SIN_STOCK',
        'PLATO_PRECIO_MODIFICADO',
        'PLATO_CAMBIO_MASIVO_PRECIOS',
        'PLATO_SOFT_DELETE',
        'LOGIN_FALLIDO_REITERADO',
        'USUARIO_CREADO',
        'USUARIO_ROL_MODIFICADO',
        'USUARIO_ESCALAMIENTO_PRIVILEGIOS',
        'USUARIO_DESACTIVADO',
        'USUARIO_REACTIVADO',
        'USUARIO_PASSWORD_MODIFICADO',
        'ACCESO_DENEGADO',
        'AUDITORIA_ACCESO_PANEL',
        'AUDITORIA_EXPORTADA',
    })

    ACCIONES_CON_MOTIVO_OBLIGATORIO = frozenset({
        'COMANDA_PLATO_ANULADO',
        'COMANDA_PLATO_ANULADO_POST_COCINA',
        'COMANDA_ANULADA',
        'COMANDA_ANULADA_CON_PRODUCCION',
        'PAGO_ANULADO',
        'PLATO_PRECIO_MODIFICADO',
        'PLATO_CAMBIO_MASIVO_PRECIOS',
        'RECETA_MODIFICADA',
        'RECETA_INSUMO_ELIMINADO',
        'CAJA_CIERRE_FORZADO',
        'CAJA_TURNO_REABIERTO',
        'PAGO_SOFT_DELETE',
        'PLATO_SOFT_DELETE',
        'INVENTARIO_AJUSTE_MANUAL_ELEVADO',
    })

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

        return cls._crear_registro(
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
        )

    @classmethod
    def _registrar_legacy(
        cls,
        usuario,
        accion,
        entidad,
        entidad_id,
        detalle_anterior=None,
        detalle_nuevo=None,
        request=None,
    ):
        """Puente privado hasta reemplazar las llamadas historicas."""
        return cls._crear_registro(
            usuario=usuario,
            accion=accion,
            modulo=entidad,
            entidad=entidad,
            entidad_id=entidad_id,
            severidad=AuditLog.Severidad.INFO,
            estado_resultado=AuditLog.EstadoResultado.EXITOSO,
            descripcion='',
            motivo=None,
            valores_anteriores=detalle_anterior,
            valores_nuevos=detalle_nuevo,
            rol=getattr(getattr(usuario, 'rol', None), 'nombre', None),
            impacto_economico_estimado=None,
            metadata=cls._resolver_metadata(request, {}),
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
            **metadata,
        )

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

    @staticmethod
    def listar_logs(
        search='',
        entidad='',
        accion='',
        modulo='',
        severidad='',
        estado_resultado='',
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

        if estado_resultado:
            logs = logs.filter(estado_resultado=estado_resultado)

        if estado_revision:
            logs = logs.filter(estado_revision=estado_revision)

        return logs
