import pytest
from django.contrib import admin
from django.test import RequestFactory

from apps.auditoria.models import AuditLog
from apps.auditoria.services import AuditoriaService
from apps.usuarios.models import AuditLog as AuditLogLegado
from apps.usuarios.utils import log_auditoria


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
