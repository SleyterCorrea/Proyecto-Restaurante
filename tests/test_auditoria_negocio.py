from datetime import timedelta
from decimal import Decimal

import pytest
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.auditoria.models import AuditLog
from apps.auditoria.services import AuditoriaService
from apps.caja.models import CajaTurno, Pago
from apps.caja.services import CajaService
from apps.comandas.models import Comanda, LineaComanda
from apps.comandas.services import CocinaService, ComandaService
from apps.core.exceptions import DatosInvalidos
from apps.inventario.models import MovimientoInventario
from apps.inventario.services import InventarioService
from apps.menu.serializers import PlatoSerializer
from apps.menu.services import MenuService
from apps.usuarios.services import UsuarioService


@pytest.mark.django_db
def test_alerta_activa_no_se_duplica_y_reaparece_solo_tras_resolverse(
    usuario_admin,
):
    datos = dict(
        usuario=usuario_admin,
        accion='INVENTARIO_STOCK_BAJO_PERSISTENTE',
        modulo='INVENTARIO',
        entidad='INSUMO',
        entidad_id=91,
        severidad=AuditLog.Severidad.ADVERTENCIA,
        estado_resultado=AuditLog.EstadoResultado.EXITOSO,
        descripcion='Stock bajo persistente.',
        deduplicar_alerta=True,
    )

    primero = AuditoriaService.registrar(**datos)
    segundo = AuditoriaService.registrar(**datos)

    assert primero.id == segundo.id
    assert AuditLog.objects.count() == 1

    AuditoriaService.resolver_alerta(
        accion=datos['accion'], entidad='INSUMO', entidad_id=91
    )
    tercero = AuditoriaService.registrar(**datos)

    assert tercero.id != primero.id
    assert AuditLog.objects.count() == 2


@pytest.mark.django_db
def test_caja_respeta_margen_y_distingue_cierre_forzado(usuario_cajero):
    turno = CajaService.abrir_turno({'saldo_inicial': 100}, usuario_cajero)
    CajaService.cerrar_turno({
        'saldo_final': 100,
        'arqueo_fisico': Decimal('100.50'),
    }, usuario_cajero)

    assert not AuditLog.objects.filter(
        accion='CAJA_DESCUADRE_DETECTADO', entidad_id=turno.id
    ).exists()

    reabierto = CajaService.reabrir_turno(
        turno.id, usuario_cajero, 'Correccion de arqueo.'
    )
    assert reabierto.estado == CajaTurno.Estado.ABIERTA

    with pytest.raises(DatosInvalidos):
        CajaService.cerrar_turno({'forzar': True}, usuario_cajero)

    CajaService.cerrar_turno({
        'forzar': True,
        'motivo': 'Cierre autorizado por contingencia.',
        'saldo_final': 100,
    }, usuario_cajero)
    assert AuditLog.objects.filter(
        accion='CAJA_CIERRE_FORZADO', entidad_id=turno.id
    ).count() == 1


@pytest.mark.django_db
def test_correcciones_pago_auditan_y_conservan_totales(
    usuario_cajero, turno_caja_abierto, mesa_libre, metodos_pago
):
    comanda = Comanda.objects.create(
        mesa=mesa_libre,
        mozo=usuario_cajero,
        codigo_comanda='AUD-PAGO',
        estado=Comanda.Estado.COBRADA,
        total=Decimal('30'),
    )
    efectivo = metodos_pago.get(codigo='EFECTIVO')
    tarjeta = metodos_pago.get(codigo='TARJETA')
    pago = Pago.objects.create(
        caja_turno=turno_caja_abierto,
        comanda=comanda,
        metodo_pago=efectivo,
        monto=Decimal('30'),
    )
    turno_caja_abierto.total_ventas = Decimal('30')
    turno_caja_abierto.total_efectivo = Decimal('30')
    turno_caja_abierto.save(update_fields=['total_ventas', 'total_efectivo'])

    CajaService.modificar_metodo_pago(
        pago.id, tarjeta.id, usuario_cajero, 'Correccion del voucher.'
    )
    CajaService.anular_pago(pago.id, usuario_cajero, 'Pago duplicado.')
    CajaService.eliminar_pago(
        pago.id, usuario_cajero, 'Depuracion del pago anulado.'
    )

    pago.refresh_from_db()
    turno_caja_abierto.refresh_from_db()
    assert pago.estado == Pago.Estado.ANULADO
    assert pago.activo is False
    assert turno_caja_abierto.total_ventas == 0
    assert turno_caja_abierto.total_tarjeta == 0
    assert list(AuditLog.objects.filter(entidad='PAGO').values_list(
        'accion', flat=True
    )) == ['PAGO_SOFT_DELETE', 'PAGO_ANULADO', 'PAGO_METODO_MODIFICADO']


@pytest.mark.django_db
def test_inventario_alertas_persistentes_se_resuelven_y_no_se_duplican(
    usuario_admin, insumo_con_stock
):
    desde = timezone.now() - timedelta(hours=49)
    type(insumo_con_stock).objects.filter(pk=insumo_con_stock.pk).update(
        stock_real=0,
        agotado_desde=desde,
    )
    insumo_con_stock.refresh_from_db()

    InventarioService.evaluar_alertas_stock(insumo_con_stock, usuario_admin)
    InventarioService.evaluar_alertas_stock(insumo_con_stock, usuario_admin)
    assert AuditLog.objects.filter(
        accion='INVENTARIO_INSUMO_AGOTADO_SIN_REPOSICION'
    ).count() == 1

    type(insumo_con_stock).objects.filter(pk=insumo_con_stock.pk).update(stock_real=10)
    insumo_con_stock.refresh_from_db()
    InventarioService.evaluar_alertas_stock(insumo_con_stock, usuario_admin)
    assert not AuditLog.objects.get(
        accion='INVENTARIO_INSUMO_AGOTADO_SIN_REPOSICION'
    ).alerta_activa

    type(insumo_con_stock).objects.filter(pk=insumo_con_stock.pk).update(
        stock_real=0, agotado_desde=desde
    )
    insumo_con_stock.refresh_from_db()
    InventarioService.evaluar_alertas_stock(insumo_con_stock, usuario_admin)
    assert AuditLog.objects.filter(
        accion='INVENTARIO_INSUMO_AGOTADO_SIN_REPOSICION'
    ).count() == 2


@pytest.mark.django_db
def test_inventario_detecta_merma_ajustes_lote_y_variacion_costo(
    usuario_admin, insumo_con_stock
):
    insumo_con_stock.costo_unitario = Decimal('10')
    insumo_con_stock.save(update_fields=['costo_unitario'])

    InventarioService.registrar_merma(
        insumo_con_stock.id,
        Decimal('1'),
        MovimientoInventario.CausaMerma.ERROR,
        usuario_admin,
        'Error de preparacion.',
    )
    for _ in range(3):
        InventarioService.ajustar(
            insumo_con_stock.id,
            Decimal('0.1'),
            MovimientoInventario.TipoMovimiento.AJUSTE_POS,
            'Conteo fisico.',
            usuario_admin,
        )
    InventarioService.reponer(
        insumo_con_stock.id, 1, usuario_admin, lote='L-001', costo_unitario=10
    )
    InventarioService.reponer(
        insumo_con_stock.id, 1, usuario_admin, lote='L-001', costo_unitario=13
    )

    acciones = set(AuditLog.objects.values_list('accion', flat=True))
    assert 'INVENTARIO_MERMA_ELEVADA' in acciones
    assert 'INVENTARIO_AJUSTES_REPETIDOS' in acciones
    assert 'INVENTARIO_LOTE_REPETIDO' in acciones
    assert 'INVENTARIO_COSTO_UNITARIO_VARIACION_ALTA' in acciones


@pytest.mark.django_db
def test_cinco_bloqueos_stock_generan_una_sola_alerta(
    usuario_mozo, insumo_con_stock
):
    cache.clear()
    for _ in range(7):
        InventarioService.registrar_bloqueo_stock(
            insumo_con_stock, usuario_mozo, requerido=20
        )

    assert AuditLog.objects.filter(
        accion='INVENTARIO_STOCK_INSUFICIENTE_REITERADO'
    ).count() == 1


@pytest.mark.django_db
def test_menu_rechaza_motivo_faltante_y_detecta_reactivacion_sin_stock(
    usuario_admin, plato_con_receta, insumo_con_stock
):
    serializer = PlatoSerializer(
        plato_con_receta,
        data={'precio_actual': '18.00'},
        partial=True,
    )
    serializer.is_valid(raise_exception=True)
    with pytest.raises(DatosInvalidos):
        MenuService.guardar_plato(serializer, usuario=usuario_admin)

    insumo_con_stock.stock_real = 0
    insumo_con_stock.save(update_fields=['stock_real'])
    plato_con_receta.refresh_from_db()
    assert plato_con_receta.disponible is False

    serializer = PlatoSerializer(
        plato_con_receta,
        data={'disponible': True},
        partial=True,
    )
    serializer.is_valid(raise_exception=True)
    MenuService.guardar_plato(
        serializer,
        usuario=usuario_admin,
        motivo='Se intenta reactivar el plato para validar su cobertura.',
    )
    plato_con_receta.refresh_from_db()

    assert plato_con_receta.disponible is False
    assert AuditLog.objects.filter(
        accion='PLATO_REACTIVADO_SIN_STOCK'
    ).count() == 1


@pytest.mark.django_db
def test_login_fallido_reiterado_se_registra_una_vez(client, usuario_mozo):
    cache.clear()
    for _ in range(6):
        response = client.post('/api/auth/login/', {
            'username': usuario_mozo.username,
            'password': 'incorrecta',
        }, content_type='application/json')
        assert response.status_code == 401

    assert AuditLog.objects.filter(
        accion='LOGIN_FALLIDO_REITERADO', usuario=usuario_mozo
    ).count() == 1


@pytest.mark.django_db
def test_flujo_normal_comanda_y_cocina_no_llena_auditoria(
    usuario_mozo, usuario_cocinero, mesa_libre, plato_con_receta
):
    comanda = ComandaService.abrir({
        'mesa_id': mesa_libre.id,
        'items': [{'plato_id': plato_con_receta.id, 'cantidad': 1}],
    }, usuario_mozo)
    linea = comanda.lineas.get()
    CocinaService.cambiar_estado(
        linea.id, LineaComanda.Estado.EN_PREP, usuario_cocinero
    )
    CocinaService.cambiar_estado(
        linea.id, LineaComanda.Estado.LISTO, usuario_cocinero
    )

    assert not AuditLog.objects.exists()


@pytest.mark.django_db
def test_anulacion_comanda_con_produccion_exige_motivo_y_audita(
    usuario_mozo, mesa_libre, plato_con_receta
):
    comanda = ComandaService.abrir({
        'mesa_id': mesa_libre.id,
        'items': [{'plato_id': plato_con_receta.id, 'cantidad': 1}],
    }, usuario_mozo)

    with pytest.raises(DatosInvalidos):
        ComandaService.anular(comanda.id, usuario_mozo, '')

    ComandaService.anular(
        comanda.id, usuario_mozo, 'Cliente cancelo luego del envio a cocina.'
    )
    comanda.refresh_from_db()
    assert comanda.estado == Comanda.Estado.ANULADA
    assert AuditLog.objects.filter(
        accion='COMANDA_ANULADA_CON_PRODUCCION', entidad_id=comanda.id
    ).count() == 1


@pytest.mark.django_db
def test_ascenso_a_rol_superior_es_escalamiento(
    client, usuario_admin, usuario_mozo, db_roles
):
    client.force_login(usuario_admin)
    response = client.patch(
        f'/api/trabajadores/{usuario_mozo.id}/',
        {'rol': db_roles['CAJERO'].id},
        content_type='application/json',
    )

    assert response.status_code == 200
    assert AuditLog.objects.filter(
        accion='USUARIO_ESCALAMIENTO_PRIVILEGIOS',
        entidad_id=usuario_mozo.id,
    ).exists()


@pytest.mark.django_db
def test_servicio_rechaza_evento_con_motivo_obligatorio(usuario_admin):
    with pytest.raises(ValidationError):
        AuditoriaService.registrar(
            usuario=usuario_admin,
            accion='COMANDA_ANULADA',
            modulo='COMANDAS',
            entidad='COMANDA',
            entidad_id=1,
            severidad=AuditLog.Severidad.ADVERTENCIA,
            estado_resultado=AuditLog.EstadoResultado.EXITOSO,
            descripcion='Anulacion sin motivo.',
        )
