import pytest
from django.contrib import admin
from django.core.exceptions import ValidationError
from django.test import RequestFactory

from apps.auditoria.models import AuditLog
from apps.auditoria.services import AuditoriaService
from apps.usuarios.models import AuditLog as AuditLogLegado
from apps.usuarios.utils import log_auditoria


ACCIONES_ESPERADAS = {
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
}


@pytest.mark.django_db
def test_audit_log_pertenece_a_auditoria_y_conserva_alias_temporal():
    assert AuditLogLegado is AuditLog
    assert AuditLog._meta.app_label == 'auditoria'
    assert AuditLog._meta.db_table == 'audit_log'
    assert AuditLog in admin.site._registry


@pytest.mark.django_db
def test_flujo_legado_completa_contexto_del_evento(usuario_admin):
    request = RequestFactory().post(
        '/admin-panel/mesas/',
        HTTP_USER_AGENT='pytest-auditoria',
    )
    request.META['REMOTE_ADDR'] = '127.0.0.1'

    log = log_auditoria(
        usuario_admin,
        'EDICION',
        'MESAS',
        10,
        detalle_nuevo={'estado': 'LIBRE'},
        request=request,
    )

    assert isinstance(log, AuditLog)
    assert log.rol == 'ADMIN'
    assert log.modulo == 'MESAS'
    assert log.codigo_evento == 'EDICION'
    assert log.severidad == AuditLog.Severidad.INFO
    assert log.ruta == '/admin-panel/mesas/'
    assert log.metodo_http == 'POST'
    assert log.ip == '127.0.0.1'
    assert AuditoriaService.listar_logs(accion='EDICION').get() == log


def test_catalogo_oficial_contiene_solo_las_acciones_aprobadas():
    assert AuditoriaService.ACCIONES_PERMITIDAS == ACCIONES_ESPERADAS


@pytest.mark.django_db
def test_registrar_evento_oficial_completa_request_y_contexto(usuario_admin):
    request = RequestFactory().post(
        '/api/usuarios/',
        HTTP_USER_AGENT='pytest-servicio-auditoria',
        HTTP_X_FORWARDED_FOR='198.51.100.20, 10.0.0.1',
    )

    log = AuditoriaService.registrar(
        usuario=usuario_admin,
        accion='USUARIO_CREADO',
        modulo='USUARIOS',
        entidad='USUARIO',
        entidad_id=25,
        severidad=AuditLog.Severidad.INFO,
        estado_resultado=AuditLog.EstadoResultado.EXITOSO,
        descripcion='Se creo un usuario desde administracion.',
        valores_anteriores=None,
        valores_nuevos={'username': 'nuevo'},
        request=request,
        datos_contextuales={
            'ip': '203.0.113.50',
            'impacto_economico_estimado': '0.00',
        },
    )

    assert log.accion == 'USUARIO_CREADO'
    assert log.codigo_evento == 'USUARIO_CREADO'
    assert log.modulo == 'USUARIOS'
    assert log.estado_resultado == AuditLog.EstadoResultado.EXITOSO
    assert log.detalle_nuevo == {'username': 'nuevo'}
    assert log.ip == '198.51.100.20'
    assert log.user_agent == 'pytest-servicio-auditoria'
    assert log.ruta == '/api/usuarios/'
    assert log.metodo_http == 'POST'
    assert str(log.impacto_economico_estimado) == '0.00'


@pytest.mark.django_db
def test_registrar_rechaza_accion_no_definida(usuario_admin):
    with pytest.raises(ValidationError, match='Accion de auditoria no permitida'):
        AuditoriaService.registrar(
            usuario=usuario_admin,
            accion='ACCION_INVENTADA',
            modulo='PRUEBAS',
            entidad='PRUEBA',
            entidad_id=1,
            severidad=AuditLog.Severidad.INFO,
            estado_resultado=AuditLog.EstadoResultado.FALLIDO,
            descripcion='No debe persistirse.',
        )

    assert not AuditLog.objects.filter(accion='ACCION_INVENTADA').exists()


@pytest.mark.django_db
@pytest.mark.parametrize(
    'accion',
    sorted(AuditoriaService.ACCIONES_CON_MOTIVO_OBLIGATORIO),
)
def test_registrar_rechaza_eventos_sensibles_sin_motivo(usuario_admin, accion):
    with pytest.raises(ValidationError, match='El motivo es obligatorio'):
        AuditoriaService.registrar(
            usuario=usuario_admin,
            accion=accion,
            modulo='PRUEBAS',
            entidad='PRUEBA',
            entidad_id=1,
            severidad=AuditLog.Severidad.CRITICA,
            estado_resultado=AuditLog.EstadoResultado.DENEGADO,
            descripcion='Evento sensible sin justificacion.',
            motivo='   ',
        )

    assert not AuditLog.objects.filter(accion=accion).exists()


@pytest.mark.django_db
def test_registrar_acepta_evento_sensible_con_motivo(usuario_admin):
    log = AuditoriaService.registrar(
        usuario=usuario_admin,
        accion='PAGO_ANULADO',
        modulo='CAJA',
        entidad='PAGO',
        entidad_id=77,
        severidad=AuditLog.Severidad.CRITICA,
        estado_resultado=AuditLog.EstadoResultado.EXITOSO,
        descripcion='Se anulo el pago por duplicidad.',
        motivo='Pago registrado dos veces.',
    )

    assert log.motivo == 'Pago registrado dos veces.'
