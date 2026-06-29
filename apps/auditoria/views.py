from django.core.exceptions import ValidationError
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import render

from rest_framework.decorators import api_view, permission_classes
from rest_framework import status
from rest_framework.response import Response

from apps.usuarios.decorators import rol_requerido

from .models import AuditLog
from .serializers import (
    AuditLogDetailSerializer,
    AuditLogFilterOptionsSerializer,
    AuditLogSerializer,
)
from .services import AuditoriaService


@login_required
@rol_requerido('ADMIN')
def admin_auditoria(request):
    # El acceso normal del administrador al panel es una operacion esperada,
    # no un evento de riesgo, perdida ni manipulacion. No se registra en
    # auditoria para no contaminar el modulo con ruido operativo ni inflar el
    # contador de pendientes. Los accesos NO autorizados si quedan registrados
    # como ACCESO_DENEGADO: en la vista HTML por el decorador rol_requerido y
    # en la API por _validar_admin_api.
    return render(request, 'admin_panel/auditoria.html')


@api_view(['GET'])
def api_auditoria_logs(request):
    permiso = _validar_admin_api(request)
    if permiso:
        return permiso

    try:
        logs = AuditoriaService.listar_logs(
            search=request.GET.get('search', '').strip(),
            fecha_desde=request.GET.get('fecha_desde', '').strip(),
            fecha_hasta=request.GET.get('fecha_hasta', '').strip(),
            turno_caja=request.GET.get('turno_caja', '').strip(),
            usuario_id=request.GET.get('usuario', '').strip(),
            rol=request.GET.get('rol', '').strip(),
            entidad=request.GET.get('entidad', '').strip(),
            entidad_id=request.GET.get('entidad_id', '').strip(),
            accion=request.GET.get('accion', '').strip() or request.GET.get('tipo_evento', '').strip(),
            modulo=request.GET.get('modulo', '').strip(),
            severidad=request.GET.get('severidad', '').strip(),
            motivo_obligatorio=request.GET.get('motivo_obligatorio', '').strip().lower(),
            estado_resultado=request.GET.get('estado_resultado', '').strip(),
            estado_revision=request.GET.get('estado_revision', '').strip(),
            responsable_revision_id=request.GET.get('responsable_revision', '').strip(),
            mesa=request.GET.get('mesa', '').strip(),
            plato=request.GET.get('plato', '').strip(),
            insumo=request.GET.get('insumo', '').strip(),
        )[:500]
    except ValidationError as exc:
        return Response(exc.message_dict, status=status.HTTP_400_BAD_REQUEST)

    serializer = AuditLogSerializer(logs, many=True)
    return Response(serializer.data)


@api_view(['GET'])
def api_auditoria_log_detalle(request, log_id):
    permiso = _validar_admin_api(request)
    if permiso:
        return permiso

    try:
        log = AuditoriaService.obtener_log(log_id)
    except AuditLog.DoesNotExist as exc:
        raise Http404('Log de auditoria no encontrado.') from exc

    serializer = AuditLogDetailSerializer(log)
    return Response(serializer.data)


@api_view(['POST', 'PATCH'])
def api_auditoria_log_revision(request, log_id):
    permiso = _validar_admin_api(request)
    if permiso:
        return permiso

    try:
        log = AuditoriaService.actualizar_estado_revision(
            log_id=log_id,
            nuevo_estado=request.data.get('estado_revision'),
            responsable=request.user,
        )
    except AuditLog.DoesNotExist as exc:
        raise Http404('Log de auditoria no encontrado.') from exc
    except ValidationError as exc:
        detalle = getattr(exc, 'message_dict', None) or {'detail': exc.messages}
        return Response(detalle, status=status.HTTP_400_BAD_REQUEST)

    serializer = AuditLogDetailSerializer(log)
    return Response(serializer.data)


@api_view(['GET'])
def api_auditoria_filtros(request):
    permiso = _validar_admin_api(request)
    if permiso:
        return permiso

    serializer = AuditLogFilterOptionsSerializer(
        AuditoriaService.obtener_opciones_filtro()
    )
    return Response(serializer.data)


@api_view(['GET'])
def api_auditoria_exportar(request):
    permiso = _validar_admin_api(request)
    if permiso:
        return permiso

    try:
        logs = AuditoriaService.listar_logs(
            search=request.GET.get('search', '').strip(),
            fecha_desde=request.GET.get('fecha_desde', '').strip(),
            fecha_hasta=request.GET.get('fecha_hasta', '').strip(),
            turno_caja=request.GET.get('turno_caja', '').strip(),
            usuario_id=request.GET.get('usuario', '').strip(),
            rol=request.GET.get('rol', '').strip(),
            entidad=request.GET.get('entidad', '').strip(),
            entidad_id=request.GET.get('entidad_id', '').strip(),
            accion=request.GET.get('accion', '').strip() or request.GET.get('tipo_evento', '').strip(),
            modulo=request.GET.get('modulo', '').strip(),
            severidad=request.GET.get('severidad', '').strip(),
            motivo_obligatorio=request.GET.get('motivo_obligatorio', '').strip().lower(),
            estado_resultado=request.GET.get('estado_resultado', '').strip(),
            estado_revision=request.GET.get('estado_revision', '').strip(),
            responsable_revision_id=request.GET.get('responsable_revision', '').strip(),
            mesa=request.GET.get('mesa', '').strip(),
            plato=request.GET.get('plato', '').strip(),
            insumo=request.GET.get('insumo', '').strip(),
        )[:2000]
    except ValidationError as exc:
        return Response(exc.message_dict, status=status.HTTP_400_BAD_REQUEST)

    AuditoriaService.registrar(
        usuario=request.user,
        accion='AUDITORIA_EXPORTADA',
        modulo='AUDITORIA',
        entidad='AUDITORIA_EXPORTACION',
        entidad_id=request.user.id,
        severidad=AuditLog.Severidad.INFO,
        estado_resultado=AuditLog.EstadoResultado.EXITOSO,
        descripcion='Exportacion de registros de auditoria.',
        valores_nuevos={'cantidad_registros': logs.count()},
        request=request,
    )
    return AuditoriaService.exportar_logs_csv(logs)


def _validar_admin_api(request):
    if not request.user or not request.user.is_authenticated:
        return Response(
            {'detail': 'Las credenciales de autenticacion no se proveyeron.'},
            status=status.HTTP_403_FORBIDDEN,
        )

    if getattr(request.user.rol, 'nombre', None) == 'ADMIN':
        return None

    AuditoriaService.registrar(
        usuario=request.user,
        accion='ACCESO_DENEGADO',
        modulo='AUDITORIA',
        entidad='AUDITORIA_API',
        entidad_id=request.user.id,
        severidad=AuditLog.Severidad.ADVERTENCIA,
        estado_resultado=AuditLog.EstadoResultado.DENEGADO,
        descripcion='Intento no autorizado de acceso a la API de auditoria.',
        request=request,
    )
    return Response(
        {'detail': 'No tienes permisos para acceder a este recurso.'},
        status=status.HTTP_403_FORBIDDEN,
    )
