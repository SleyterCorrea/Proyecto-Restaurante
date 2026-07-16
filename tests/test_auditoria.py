import pytest
from io import StringIO

from django.contrib import admin
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import RequestFactory, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.auditoria.constants import ACCIONES_AUDITABLES
from apps.auditoria.models import AuditLog
from apps.auditoria.services import AuditoriaService
from apps.caja.services import CajaService
from apps.comandas.models import Comanda, ComandaHistorialEstado, LineaComanda
from apps.comandas.services import CocinaService
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
    'CAJA_VENTA_PERDIDA_REGISTRADA',
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
    'PLATO_MODIFICADO',
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
def test_adaptador_ignora_accion_legacy_sin_fallar(usuario_admin):
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

    assert log is None
    assert not AuditLog.objects.exists()


@pytest.mark.django_db
def test_adaptador_delega_accion_final_y_parametros_compatibles(usuario_admin):
    log = log_auditoria(
        usuario_admin,
        'USUARIO_CREADO',
        'USUARIO',
        10,
        detalle_anterior={'existe': False},
        valores_nuevos={'username': 'nuevo'},
        ip='127.0.0.2',
        modulo='USUARIOS',
    )

    assert isinstance(log, AuditLog)
    assert log.codigo_evento == 'USUARIO_CREADO'
    assert log.detalle_anterior == {'existe': False}
    assert log.detalle_nuevo == {'username': 'nuevo'}
    assert log.ip == '127.0.0.2'


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


@pytest.mark.django_db
def test_kds_audita_solo_anulacion_y_conserva_historial(
    usuario_cocinero,
    usuario_mozo,
    mesa_libre,
    plato_con_receta,
):
    comanda = Comanda.objects.create(
        mesa=mesa_libre,
        mozo=usuario_mozo,
        codigo_comanda='AUD-KDS',
    )
    linea = LineaComanda.objects.create(
        comanda=comanda,
        plato=plato_con_receta,
        cantidad=1,
        precio_unitario=15,
        subtotal=15,
    )
    request = RequestFactory().patch('/api/cocina/lineas/1/cambiar-estado/')

    CocinaService.cambiar_estado(
        linea.id,
        LineaComanda.Estado.EN_PREP,
        usuario_cocinero,
        request=request,
    )
    assert ComandaHistorialEstado.objects.count() == 1
    assert not AuditLog.objects.exists()

    CocinaService.cambiar_estado(
        linea.id,
        LineaComanda.Estado.ANULADO,
        usuario_cocinero,
        motivo='Ingrediente no disponible.',
        request=request,
    )

    assert ComandaHistorialEstado.objects.count() == 2
    log = AuditLog.objects.get()
    assert log.accion == 'COMANDA_PLATO_ANULADO_POST_COCINA'
    assert log.motivo == 'Ingrediente no disponible.'


@pytest.mark.django_db
def test_caja_audita_turno_y_descuadre(usuario_cajero):
    turno = CajaService.abrir_turno({'saldo_inicial': 100}, usuario_cajero)
    CajaService.cerrar_turno({
        'saldo_final': 90,
        'arqueo_fisico': 90,
    }, usuario_cajero)

    assert list(
        AuditLog.objects.filter(entidad_id=turno.id)
        .order_by('fecha_evento')
        .values_list('accion', flat=True)
    ) == [
        'CAJA_TURNO_ABIERTO',
        'CAJA_TURNO_CERRADO',
        'CAJA_DESCUADRE_DETECTADO',
    ]


@pytest.mark.django_db
def test_endpoints_registran_usuario_y_precio(
    client,
    usuario_admin,
    db_roles,
    plato_con_receta,
):
    client.force_login(usuario_admin)
    response = client.post('/api/trabajadores/', {
        'username': 'auditable',
        'email': 'auditable@test.com',
        'nombres': 'Usuario',
        'apellidos': 'Auditable',
        'rol': db_roles['MOZO'].id,
        'password': 'pass12345',
    })
    assert response.status_code == 201
    assert AuditLog.objects.filter(accion='USUARIO_CREADO').exists()

    response = client.patch(
        f'/api/menu/platos/{plato_con_receta.id}/',
        {'precio_actual': '18.00'},
        content_type='application/json',
    )
    assert response.status_code == 400
    plato_con_receta.refresh_from_db()
    assert str(plato_con_receta.precio_actual) == '15.00'

    response = client.patch(
        f'/api/menu/platos/{plato_con_receta.id}/',
        {
            'precio_actual': '18.00',
            'motivo': 'Actualizacion por costo de insumos.',
        },
        content_type='application/json',
    )
    assert response.status_code == 200
    assert AuditLog.objects.filter(
        accion='PLATO_PRECIO_MODIFICADO',
        entidad_id=plato_con_receta.id,
    ).exists()


@pytest.mark.django_db
def test_api_auditoria_admin_puede_filtrar_detallar_y_exportar(
    client,
    usuario_admin,
    usuario_cajero,
):
    log_turno = AuditoriaService.registrar(
        usuario=usuario_admin,
        accion='CAJA_TURNO_ABIERTO',
        modulo='CAJA',
        entidad='CAJA_TURNO',
        entidad_id=77,
        severidad=AuditLog.Severidad.INFO,
        estado_resultado=AuditLog.EstadoResultado.EXITOSO,
        descripcion='Apertura del turno MANANA.',
        valores_nuevos={'turno': 'MANANA', 'mesa': '5', 'plato': 'Lomo', 'insumo': 'Papa'},
    )
    log_turno.estado_revision = AuditLog.EstadoRevision.REVISADO
    log_turno.responsable_revision = usuario_admin
    log_turno.save(update_fields=['estado_revision', 'responsable_revision'])

    AuditoriaService.registrar(
        usuario=usuario_cajero,
        accion='CAJA_DESCUADRE_DETECTADO',
        modulo='CAJA',
        entidad='CAJA_TURNO',
        entidad_id=78,
        severidad=AuditLog.Severidad.ADVERTENCIA,
        estado_resultado=AuditLog.EstadoResultado.EXITOSO,
        descripcion='Descuadre en turno NOCHE.',
        motivo='Faltante de caja.',
        valores_nuevos={'turno': 'NOCHE', 'mesa': '9', 'plato': 'Tallarin', 'insumo': 'Aceite'},
    )

    client.force_login(usuario_admin)

    response = client.get('/admin-panel/auditoria/')
    assert response.status_code == 200
    # El acceso normal del administrador al panel es una operacion esperada y
    # ya no se audita: no debe generar eventos AUDITORIA_ACCESO_PANEL.
    assert not AuditLog.objects.filter(accion='AUDITORIA_ACCESO_PANEL').exists()

    filtros = client.get('/admin-panel/api/auditoria-logs/filtros/')
    assert filtros.status_code == 200
    assert 'CAJA' in filtros.json()['modulos']

    listado = client.get(
        '/admin-panel/api/auditoria-logs/',
        {
            'fecha_desde': timezone.localtime(log_turno.fecha_evento).strftime('%Y-%m-%d'),
            'fecha_hasta': timezone.localtime(log_turno.fecha_evento).strftime('%Y-%m-%d'),
            'turno_caja': '77',
            'usuario': str(usuario_admin.id),
            'rol': 'ADMIN',
            'modulo': 'CAJA',
            'severidad': 'INFO',
            'tipo_evento': 'CAJA_TURNO_ABIERTO',
            'entidad': 'CAJA_TURNO',
            'entidad_id': '77',
            'mesa': '5',
            'plato': 'Lomo',
            'insumo': 'Papa',
            'motivo_obligatorio': 'false',
            'estado_revision': AuditLog.EstadoRevision.REVISADO,
            'responsable_revision': str(usuario_admin.id),
        },
    )
    data = listado.json()
    assert listado.status_code == 200
    assert len(data) == 1
    assert data[0]['id'] == log_turno.id

    detalle = client.get(f'/admin-panel/api/auditoria-logs/{log_turno.id}/')
    assert detalle.status_code == 200
    assert detalle.json()['codigo_evento'] == 'CAJA_TURNO_ABIERTO'

    exportacion = client.get(
        '/admin-panel/api/auditoria-logs/export/',
        {'tipo_evento': 'CAJA_TURNO_ABIERTO'},
    )
    assert exportacion.status_code == 200
    assert exportacion['Content-Type'].startswith('text/csv')
    assert AuditLog.objects.filter(accion='AUDITORIA_EXPORTADA').exists()


@pytest.mark.django_db
def test_api_auditoria_deniega_a_no_admin(client, usuario_cajero):
    client.force_login(usuario_cajero)

    response = client.get(reverse('api_auditoria_logs'))

    assert response.status_code == 403
    assert AuditLog.objects.filter(
        accion='ACCESO_DENEGADO',
        usuario=usuario_cajero,
        modulo='AUDITORIA',
    ).exists()


@pytest.mark.django_db
def test_admin_actualiza_estado_revision(client, usuario_admin):
    log = AuditoriaService.registrar(
        usuario=usuario_admin,
        accion='CAJA_DESCUADRE_DETECTADO',
        modulo='CAJA',
        entidad='CAJA_TURNO',
        entidad_id=501,
        severidad=AuditLog.Severidad.CRITICA,
        estado_resultado=AuditLog.EstadoResultado.EXITOSO,
        descripcion='Descuadre de prueba.',
        motivo='Faltante de caja.',
    )
    assert log.estado_revision == AuditLog.EstadoRevision.PENDIENTE

    client.force_login(usuario_admin)
    response = client.post(
        f'/admin-panel/api/auditoria-logs/{log.id}/revision/',
        {'estado_revision': 'REVISADO'},
        content_type='application/json',
    )

    assert response.status_code == 200
    assert response.json()['estado_revision'] == 'REVISADO'
    assert response.json()['responsable_revision'] == usuario_admin.username

    log.refresh_from_db()
    assert log.estado_revision == AuditLog.EstadoRevision.REVISADO
    assert log.responsable_revision_id == usuario_admin.id


@pytest.mark.django_db
def test_revision_rechaza_estado_invalido(client, usuario_admin):
    log = AuditoriaService.registrar(
        usuario=usuario_admin,
        accion='PAGO_ANULADO',
        modulo='CAJA',
        entidad='PAGO',
        entidad_id=502,
        severidad=AuditLog.Severidad.CRITICA,
        estado_resultado=AuditLog.EstadoResultado.EXITOSO,
        descripcion='Pago anulado de prueba.',
        motivo='Cobro duplicado.',
    )

    client.force_login(usuario_admin)
    response = client.post(
        f'/admin-panel/api/auditoria-logs/{log.id}/revision/',
        {'estado_revision': 'ESTADO_FALSO'},
        content_type='application/json',
    )

    assert response.status_code == 400
    log.refresh_from_db()
    assert log.estado_revision == AuditLog.EstadoRevision.PENDIENTE


@pytest.mark.django_db
def test_no_admin_no_puede_actualizar_estado_revision(client, usuario_admin, usuario_cajero):
    log = AuditoriaService.registrar(
        usuario=usuario_admin,
        accion='CAJA_DESCUADRE_DETECTADO',
        modulo='CAJA',
        entidad='CAJA_TURNO',
        entidad_id=503,
        severidad=AuditLog.Severidad.CRITICA,
        estado_resultado=AuditLog.EstadoResultado.EXITOSO,
        descripcion='Descuadre de prueba.',
        motivo='Faltante de caja.',
    )

    client.force_login(usuario_cajero)
    response = client.post(
        f'/admin-panel/api/auditoria-logs/{log.id}/revision/',
        {'estado_revision': 'REVISADO'},
        content_type='application/json',
    )

    assert response.status_code == 403
    log.refresh_from_db()
    assert log.estado_revision == AuditLog.EstadoRevision.PENDIENTE


@override_settings(DEBUG=True)
@pytest.mark.django_db
def test_seed_auditoria_demo_cubre_acciones_sin_mesas(usuario_admin):
    call_command('seed_auditoria_demo', stdout=StringIO())

    demo = AuditLog.objects.filter(clave_alerta='DEMO_AUDITORIA')
    generadas = set(demo.values_list('codigo_evento', flat=True))
    esperadas = ACCIONES_AUDITABLES - {'AUDITORIA_ACCESO_PANEL'}

    # 1. cubre todas las acciones esperadas, sin faltantes
    assert generadas == esperadas
    # 2. no genera la accion operativa excluida
    assert 'AUDITORIA_ACCESO_PANEL' not in generadas
    # 3. no genera registros del modulo MESAS
    assert not demo.filter(modulo='MESAS').exists()
    # marca de limpieza presente en cada registro demo
    assert demo.count() == len(esperadas)

    # --reset-demo elimina solo los registros demo
    call_command('seed_auditoria_demo', '--reset-demo', stdout=StringIO())
    assert not AuditLog.objects.filter(clave_alerta='DEMO_AUDITORIA').exists()
