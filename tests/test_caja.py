import pytest
from django.urls import reverse
from rest_framework import status
from apps.comandas.models import Comanda, LineaComanda
from apps.caja.models import CajaTurno, Pago, MetodoPago
from apps.mesas.models import Mesa

@pytest.mark.django_db
def test_cobrar_no_descuenta_insumos_en_caja(client, usuario_cajero, turno_caja_abierto, mesa_libre, plato_con_receta, insumo_con_stock, metodos_pago):
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
    assert float(insumo_con_stock.stock_real) == stock_inicial
    
    comanda.refresh_from_db()
    assert comanda.estado == Comanda.Estado.COBRADA
    
    mesa_libre.refresh_from_db()
    assert mesa_libre.estado == Mesa.Estado.LIBRE
    
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
