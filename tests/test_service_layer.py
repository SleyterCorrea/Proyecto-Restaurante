from decimal import Decimal

import pytest

from apps.caja.models import CajaTurno
from apps.caja.services import CajaService
from apps.comandas.models import Comanda, LineaComanda
from apps.comandas.services import CocinaService, ComandaService
from apps.core.exceptions import CajaNoAbierta, DatosInvalidos
from apps.inventario.models import MovimientoInventario, OrdenCompra
from apps.inventario.services import InventarioService
from apps.menu.serializers import CategoriaSerializer, PlatoSerializer
from apps.menu.services import MenuService
from apps.mesas.models import Mesa, Zona
from apps.mesas.services import MesaService


@pytest.mark.django_db
def test_comanda_service_ciclo_de_edicion(usuario_mozo, mesa_libre, plato_con_receta):
    comanda = ComandaService.abrir({
        'mesa_id': mesa_libre.id,
        'items': [{'plato_id': plato_con_receta.id, 'cantidad': 1}],
    }, usuario_mozo)

    nueva = ComandaService.agregar_plato(comanda.id, {
        'plato_id': plato_con_receta.id, 'cantidad': 1, 'notas': 'Sin sal',
    })
    editada = ComandaService.editar_linea(nueva.id, {'cantidad': 2})
    assert editada.cantidad == 2
    assert editada.observacion == 'Sin sal'

    ComandaService.eliminar_linea(nueva.id)
    assert comanda.lineas.count() == 1


@pytest.mark.django_db
def test_cocina_service_actualiza_comanda_y_no_descuenta_stock(
    usuario_cocinero, usuario_mozo, mesa_libre, plato_con_receta, insumo_con_stock
):
    comanda = Comanda.objects.create(
        mesa=mesa_libre, mozo=usuario_mozo, codigo_comanda='SERV-KDS'
    )
    linea = LineaComanda.objects.create(
        comanda=comanda, plato=plato_con_receta, cantidad=1,
        precio_unitario=15, subtotal=15,
    )
    stock = insumo_con_stock.stock_real

    CocinaService.cambiar_estado(linea.id, LineaComanda.Estado.EN_PREP, usuario_cocinero)
    comanda.refresh_from_db()
    assert comanda.estado == Comanda.Estado.EN_PREPARACION

    CocinaService.cambiar_estado(linea.id, LineaComanda.Estado.LISTO, usuario_cocinero)
    insumo_con_stock.refresh_from_db()
    assert insumo_con_stock.stock_real == stock


@pytest.mark.django_db
def test_inventario_service_ajustes_merma_y_estado(usuario_admin, insumo_con_stock):
    InventarioService.reponer(insumo_con_stock.id, 2, usuario_admin, 'Compra')
    InventarioService.ajustar(
        insumo_con_stock.id, 1, MovimientoInventario.TipoMovimiento.AJUSTE_NEG,
        'Conteo', usuario_admin,
    )
    InventarioService.registrar_merma(
        insumo_con_stock.id, 1, MovimientoInventario.CausaMerma.ERROR,
        usuario_admin, 'Prueba',
    )
    insumo_con_stock.refresh_from_db()
    assert insumo_con_stock.stock_real == Decimal('10')
    assert insumo_con_stock.movimientos.count() == 3

    InventarioService.cambiar_activo(
        insumo_con_stock.id, False, motivo='Insumo retirado del catalogo de prueba.'
    )
    InventarioService.cambiar_activo(insumo_con_stock.id, True)
    insumo_con_stock.refresh_from_db()
    assert insumo_con_stock.activo is True


@pytest.mark.django_db
def test_inventario_service_orden_compra(usuario_admin, insumo_con_stock):
    orden = InventarioService.crear_orden({
        'proveedor': 'Proveedor Test',
        'items': [{
            'insumo': insumo_con_stock.id,
            'cantidad_solicitada': 3,
            'costo_unitario': 2,
        }],
    }, usuario_admin)
    assert orden.total_estimado == Decimal('6')

    InventarioService.cambiar_estado_orden(orden.id, OrdenCompra.Estado.ENVIADA)
    InventarioService.cambiar_estado_orden(
        orden.id, OrdenCompra.Estado.RECIBIDA, usuario_admin
    )
    orden.refresh_from_db()
    insumo_con_stock.refresh_from_db()
    assert orden.estado == OrdenCompra.Estado.RECIBIDA
    assert insumo_con_stock.stock_real == Decimal('13')


@pytest.mark.django_db
def test_mesa_service_union_limpieza_y_soft_delete():
    zona = Zona.objects.create(nombre='Service Layer')
    mesa1 = MesaService.crear({'numero': 1, 'capacidad': 4, 'zona_id': zona.id})
    mesa2 = MesaService.crear({'numero': 2, 'capacidad': 2, 'zona_id': zona.id})
    union = MesaService.crear_union({
        'mesa_principal_id': mesa1.id,
        'mesa_secundaria_ids': [mesa2.id],
    })
    assert union.mesas_secundarias.count() == 1
    MesaService.disolver_union(union.id)
    union.refresh_from_db()
    assert union.activa is False

    mesa1.estado = Mesa.Estado.LIMPIEZA
    mesa1.save(update_fields=['estado'])
    MesaService.marcar_limpiada(mesa1.id)
    MesaService.desactivar(mesa1.id)
    mesa1.refresh_from_db()
    assert mesa1.activo is False


@pytest.mark.django_db
def test_menu_service_receta_y_soft_delete(insumo_con_stock):
    categoria_serializer = CategoriaSerializer(data={'nombre': 'Servicio'})
    categoria_serializer.is_valid(raise_exception=True)
    categoria = MenuService.guardar_categoria(categoria_serializer)

    plato_serializer = PlatoSerializer(data={
        'nombre': 'Plato Service',
        'categoria': categoria.id,
        'precio_actual': '20.00',
        'tiempo_preparacion_min': 10,
        'disponible': True,
    })
    plato_serializer.is_valid(raise_exception=True)
    plato = MenuService.guardar_plato(plato_serializer, [{
        'insumo_id': insumo_con_stock.id,
        'cantidad_por_porcion': '0.25',
    }])
    assert plato.receta.filter(activo=True).count() == 1

    MenuService.eliminar_insumo(plato, insumo_con_stock.id)
    MenuService.desactivar_plato(plato)
    plato.refresh_from_db()
    assert plato.activo is False
    assert plato.disponible is False


@pytest.mark.django_db
def test_menu_no_publica_plato_sin_receta():
    categoria_serializer = CategoriaSerializer(data={'nombre': 'Sin receta'})
    categoria_serializer.is_valid(raise_exception=True)
    categoria = MenuService.guardar_categoria(categoria_serializer)
    plato_serializer = PlatoSerializer(data={
        'nombre': 'Plato sin receta',
        'categoria': categoria.id,
        'precio_actual': '18.00',
        'tiempo_preparacion_min': 10,
        'disponible': True,
    })
    plato_serializer.is_valid(raise_exception=True)

    with pytest.raises(DatosInvalidos, match='al menos un insumo'):
        MenuService.guardar_plato(plato_serializer, [])


@pytest.mark.django_db
def test_caja_service_apertura_y_cierre(usuario_cajero):
    turno = CajaService.abrir_turno({'saldo_inicial': 100}, usuario_cajero)
    assert turno.estado == CajaTurno.Estado.ABIERTA
    CajaService.cerrar_turno({'saldo_final': 100, 'arqueo_fisico': 100})
    turno.refresh_from_db()
    assert turno.estado == CajaTurno.Estado.CERRADA
    assert turno.diferencia == 0

    with pytest.raises(CajaNoAbierta):
        CajaService.cerrar_turno({'saldo_final': 100})


@pytest.mark.django_db
def test_comanda_valida_stock_sin_descontar_antes_del_cobro(
    usuario_mozo, mesa_libre, plato_con_receta, insumo_con_stock
):
    stock_inicial = insumo_con_stock.stock_real
    assert stock_inicial == Decimal('10')

    # La comanda valida disponibilidad, pero el consumo pertenece al cobro.
    comanda = ComandaService.abrir({
        'mesa_id': mesa_libre.id,
        'items': [{'plato_id': plato_con_receta.id, 'cantidad': 2}], # 2 * 0.5 = 1.0 kg
    }, usuario_mozo)

    insumo_con_stock.refresh_from_db()
    assert insumo_con_stock.stock_real == stock_inicial

    linea_nueva = ComandaService.agregar_plato(comanda.id, {
        'plato_id': plato_con_receta.id, 'cantidad': 1, # 1 * 0.5 = 0.5 kg
    })

    insumo_con_stock.refresh_from_db()
    assert insumo_con_stock.stock_real == stock_inicial

    ComandaService.editar_linea(linea_nueva.id, {'cantidad': 3})

    insumo_con_stock.refresh_from_db()
    assert insumo_con_stock.stock_real == stock_inicial

    ComandaService.eliminar_linea(linea_nueva.id)

    insumo_con_stock.refresh_from_db()
    assert insumo_con_stock.stock_real == stock_inicial

    ComandaService.anular(comanda.id, usuario_mozo, motivo="Cliente cancelo todo")

    insumo_con_stock.refresh_from_db()
    assert insumo_con_stock.stock_real == stock_inicial


@pytest.mark.django_db
def test_cocina_no_descuenta_ni_reintegra_stock(
    usuario_cocinero, usuario_mozo, mesa_libre, plato_con_receta, insumo_con_stock
):
    stock_inicial = insumo_con_stock.stock_real
    assert stock_inicial == Decimal('10')

    comanda = ComandaService.abrir({
        'mesa_id': mesa_libre.id,
        'items': [{'plato_id': plato_con_receta.id, 'cantidad': 2}], # 2 * 0.5 = 1.0 kg
    }, usuario_mozo)
    linea = comanda.lineas.first()

    insumo_con_stock.refresh_from_db()
    assert insumo_con_stock.stock_real == stock_inicial

    # 2. Iniciar preparación en cocina
    CocinaService.cambiar_estado(linea.id, LineaComanda.Estado.EN_PREP, usuario_cocinero)

    CocinaService.cambiar_estado(linea.id, LineaComanda.Estado.ANULADO, usuario_cocinero, motivo="Se quemó")

    insumo_con_stock.refresh_from_db()
    assert insumo_con_stock.stock_real == stock_inicial
