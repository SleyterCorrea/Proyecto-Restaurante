import pytest
from django.urls import reverse
from rest_framework import status
from apps.comandas.models import Comanda, LineaComanda
from apps.caja.models import CajaTurno, Pago, MetodoPago
from apps.mesas.models import Mesa
from apps.inventario.models import MovimientoInventario
from apps.inventario.services import InventarioService

@pytest.mark.django_db
def test_cobrar_descuenta_insumos_atomicamente(client, usuario_cajero, turno_caja_abierto, mesa_libre, plato_con_receta, insumo_con_stock, metodos_pago):
    client.force_login(usuario_cajero)
    
    # Comanda LISTA
    comanda = Comanda.objects.create(mesa=mesa_libre, mozo=usuario_cajero, codigo_comanda='C-PAGAR', estado=Comanda.Estado.LISTA)
    LineaComanda.objects.create(
        comanda=comanda, plato=plato_con_receta, cantidad=2, 
        precio_unitario=15, subtotal=30, estado=LineaComanda.Estado.LISTO
    )
    comanda.total = 30
    comanda.save()
    
    stock_inicial = float(insumo_con_stock.stock_real)

    url = reverse('api_comanda_pagar', kwargs={'pk': comanda.id})
    metodo = MetodoPago.objects.get(codigo='EFECTIVO')
    
    data = {
        'metodo_pago_id': metodo.id,
        'monto_recibido': 50
    }
    
    response = client.post(url, data, content_type='application/json')
    assert response.status_code == status.HTTP_200_OK
    
    # Verificar cambios
    insumo_con_stock.refresh_from_db()
    assert float(insumo_con_stock.stock_real) == stock_inicial - 1.0

    # El movimiento por línea hace el descuento idempotente.
    linea = comanda.lineas.get()
    assert InventarioService.descontar_lineas([linea], usuario_cajero) == 0
    insumo_con_stock.refresh_from_db()
    assert float(insumo_con_stock.stock_real) == stock_inicial - 1.0
    
    comanda.refresh_from_db()
    assert comanda.estado == Comanda.Estado.COBRADA
    
    mesa_libre.refresh_from_db()
    assert mesa_libre.estado == Mesa.Estado.LIMPIEZA
    
    turno_caja_abierto.refresh_from_db()
    assert turno_caja_abierto.total_ventas == 30

@pytest.mark.django_db
def test_no_cobrar_sin_caja_abierta(client, usuario_cajero, mesa_libre, plato_con_receta, metodos_pago):
    client.force_login(usuario_cajero)
    # Sin turno fixture
    
    comanda = Comanda.objects.create(mesa=mesa_libre, mozo=usuario_cajero, codigo_comanda='C-NO-TURNO', estado=Comanda.Estado.LISTA)
    comanda.total = 30
    comanda.save()
    
    url = reverse('api_comanda_pagar', kwargs={'pk': comanda.id})
    metodo = MetodoPago.objects.first()
    
    response = client.post(url, {'metodo_pago_id': metodo.id, 'monto_recibido': 30}, content_type='application/json')
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert 'No hay un turno de caja abierto' in response.json()['error']


@pytest.mark.django_db
def test_cobro_sin_stock_hace_rollback_completo(
    client, usuario_cajero, turno_caja_abierto, mesa_libre,
    plato_con_receta, insumo_con_stock, metodos_pago
):
    comanda = Comanda.objects.create(
        mesa=mesa_libre, mozo=usuario_cajero, codigo_comanda='C-ROLLBACK',
        estado=Comanda.Estado.LISTA, total=15,
    )
    LineaComanda.objects.create(
        comanda=comanda, plato=plato_con_receta, cantidad=1,
        precio_unitario=15, subtotal=15, estado=LineaComanda.Estado.LISTO,
    )
    insumo_con_stock.stock_real = 0
    insumo_con_stock.save(update_fields=['stock_real'])
    client.force_login(usuario_cajero)

    response = client.post(reverse('api_comanda_pagar', kwargs={'pk': comanda.id}), {
        'metodo_pago_id': metodos_pago[0].id,
        'monto_recibido': 15,
    }, content_type='application/json')

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert Pago.objects.filter(comanda=comanda).count() == 0
    assert MovimientoInventario.objects.filter(referencia_tipo='LINEA_COMANDA').count() == 0
    comanda.refresh_from_db()
    assert comanda.estado == Comanda.Estado.LISTA
