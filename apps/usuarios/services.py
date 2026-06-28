import hashlib

from django.core.cache import cache
from django.db import transaction

from apps.auditoria.constants import JERARQUIA_ROLES, obtener_umbral
from apps.auditoria.models import AuditLog
from apps.auditoria.services import AuditoriaService

from .models import Usuario


class UsuarioService:
    """Centraliza escrituras de usuarios y eventos de seguridad."""

    @staticmethod
    @transaction.atomic
    def crear(serializer, actor, request=None):
        usuario = serializer.save()
        if usuario.is_active != usuario.activo:
            usuario.is_active = usuario.activo
            usuario.save(update_fields=['is_active'])
        AuditoriaService.registrar(
            usuario=actor,
            accion='USUARIO_CREADO',
            modulo='USUARIOS',
            entidad='USUARIO',
            entidad_id=usuario.id,
            severidad=AuditLog.Severidad.INFO,
            estado_resultado=AuditLog.EstadoResultado.EXITOSO,
            descripcion=f'Se creo el usuario {usuario.username}.',
            valores_nuevos={
                'username': usuario.username,
                'rol': usuario.rol.nombre,
                'activo': usuario.activo,
            },
            request=request,
        )
        return usuario

    @staticmethod
    @transaction.atomic
    def actualizar(serializer, actor, request=None):
        instancia = serializer.instance
        anterior = {
            'rol': instancia.rol.nombre,
            'activo': instancia.activo,
        }
        password_modificado = bool(serializer.validated_data.get('password'))
        usuario = serializer.save()
        rol_nuevo = usuario.rol.nombre

        if anterior['rol'] != rol_nuevo:
            escalamiento = JERARQUIA_ROLES.get(
                rol_nuevo, 0
            ) > JERARQUIA_ROLES.get(anterior['rol'], 0)
            AuditoriaService.registrar(
                usuario=actor,
                accion=(
                    'USUARIO_ESCALAMIENTO_PRIVILEGIOS'
                    if escalamiento else 'USUARIO_ROL_MODIFICADO'
                ),
                modulo='USUARIOS',
                entidad='USUARIO',
                entidad_id=usuario.id,
                severidad=(
                    AuditLog.Severidad.CRITICA
                    if escalamiento else AuditLog.Severidad.ADVERTENCIA
                ),
                estado_resultado=AuditLog.EstadoResultado.EXITOSO,
                descripcion=(
                    f'El rol de {usuario.username} cambio de '
                    f'{anterior["rol"]} a {rol_nuevo}.'
                ),
                valores_anteriores={'rol': anterior['rol']},
                valores_nuevos={'rol': rol_nuevo},
                request=request,
            )

        if anterior['activo'] != usuario.activo:
            if usuario.is_active != usuario.activo:
                usuario.is_active = usuario.activo
                usuario.save(update_fields=['is_active'])
            AuditoriaService.registrar(
                usuario=actor,
                accion=(
                    'USUARIO_REACTIVADO'
                    if usuario.activo else 'USUARIO_DESACTIVADO'
                ),
                modulo='USUARIOS',
                entidad='USUARIO',
                entidad_id=usuario.id,
                severidad=AuditLog.Severidad.ADVERTENCIA,
                estado_resultado=AuditLog.EstadoResultado.EXITOSO,
                descripcion=f'Se cambio el estado activo de {usuario.username}.',
                valores_anteriores={'activo': anterior['activo']},
                valores_nuevos={
                    'activo': usuario.activo,
                    'is_active': usuario.is_active,
                },
                request=request,
            )

        if password_modificado:
            AuditoriaService.registrar(
                usuario=actor,
                accion='USUARIO_PASSWORD_MODIFICADO',
                modulo='USUARIOS',
                entidad='USUARIO',
                entidad_id=usuario.id,
                severidad=AuditLog.Severidad.ADVERTENCIA,
                estado_resultado=AuditLog.EstadoResultado.EXITOSO,
                descripcion=f'Se modifico la clave de {usuario.username}.',
                valores_anteriores={'password': 'PROTEGIDO'},
                valores_nuevos={'password': 'PROTEGIDO'},
                request=request,
            )
        return usuario

    @staticmethod
    @transaction.atomic
    def desactivar(usuario, actor, request=None):
        if not usuario.activo:
            return usuario
        usuario.activo = False
        usuario.is_active = False
        usuario.save(update_fields=['activo', 'is_active'])
        AuditoriaService.registrar(
            usuario=actor,
            accion='USUARIO_DESACTIVADO',
            modulo='USUARIOS',
            entidad='USUARIO',
            entidad_id=usuario.id,
            severidad=AuditLog.Severidad.ADVERTENCIA,
            estado_resultado=AuditLog.EstadoResultado.EXITOSO,
            descripcion=f'Se desactivo el usuario {usuario.username}.',
            valores_anteriores={'activo': True, 'is_active': True},
            valores_nuevos={'activo': False, 'is_active': False},
            request=request,
        )
        return usuario

    @staticmethod
    def _clave_login(username):
        digest = hashlib.sha256(
            str(username or '').strip().lower().encode('utf-8')
        ).hexdigest()
        return f'audit:login-fallido:{digest}'

    @classmethod
    def registrar_login_fallido(cls, username, request=None):
        username = str(username or '').strip()
        if not username:
            return None
        ventana = obtener_umbral('LOGIN_FALLIDOS_VENTANA_MINUTOS')
        limite = obtener_umbral('LOGIN_FALLIDOS_CANTIDAD')
        clave = cls._clave_login(username)
        cache.add(clave, 0, timeout=ventana * 60)
        intentos = cache.incr(clave)
        if intentos < limite:
            return None
        usuario = Usuario.objects.filter(username__iexact=username).first()
        return AuditoriaService.registrar(
            usuario=usuario,
            accion='LOGIN_FALLIDO_REITERADO',
            modulo='USUARIOS',
            entidad='USUARIO',
            entidad_id=usuario.id if usuario else 0,
            severidad=AuditLog.Severidad.CRITICA,
            estado_resultado=AuditLog.EstadoResultado.FALLIDO,
            descripcion='Se detectaron intentos reiterados de inicio de sesion.',
            valores_nuevos={
                'username': username,
                'intentos': intentos,
                'ventana_minutos': ventana,
            },
            request=request,
            deduplicar_durante_minutos=ventana,
        )

    @classmethod
    def registrar_login_exitoso(cls, username):
        if username:
            cache.delete(cls._clave_login(username))

    @staticmethod
    def registrar_acceso_denegado(usuario, request=None, recurso=''):
        if not usuario or not usuario.is_authenticated:
            return None
        return AuditoriaService.registrar(
            usuario=usuario,
            accion='ACCESO_DENEGADO',
            modulo='SEGURIDAD',
            entidad='USUARIO',
            entidad_id=usuario.id,
            severidad=AuditLog.Severidad.ADVERTENCIA,
            estado_resultado=AuditLog.EstadoResultado.DENEGADO,
            descripcion=f'Acceso denegado al recurso {recurso or "no identificado"}.',
            valores_nuevos={'recurso': recurso},
            request=request,
            deduplicar_durante_minutos=obtener_umbral(
                'ACCESO_DENEGADO_DEDUP_MINUTOS'
            ),
        )
