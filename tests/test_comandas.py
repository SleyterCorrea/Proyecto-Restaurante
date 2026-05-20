import pytest
from django.urls import reverse
from rest_framework import status
from apps.comandas.models import Comanda, LineaComanda
from apps.mesas.models import Mesa

@pytest.mark.django_db
def test_no_abrir_comanda_mesa_ocupada(client, usuario_mozo, mesa_libre, plato_con_receta):
    client.force_login(usuario_mozo)
    # Ocupar mesa primero
    mesa_libre.estado = Mesa.Estado.OCUPADA
    mesa_libre.save()
    
    url = reverse('api_crear_comanda')
    data = {
        'mesa_id': mesa_libre.id,
        'items': [{'plato_id': plato_con_receta.id, 'cantidad': 1}]
    }
    response = client.post(url, data, content_type='application/json')
    assert response.status_code == status.HTTP_409_CONFLICT
    assert 'no está libre' in response.json()['error']

@pytest.mark.django_db
def test_agregar_plato_sin_stock_falla(client, usuario_mozo, mesa_libre, plato_con_receta, insumo_con_stock):
    client.force_login(usuario_mozo)
    # Agotar stock
    insumo_con_stock.stock_real = 0
    insumo_con_stock.save(update_fields=['stock_real'])
    
    url = reverse('api_crear_comanda')
    data = {
        'mesa_id': mesa_libre.id,
        'items': [{'plato_id': plato_con_receta.id, 'cantidad': 1}]
    }
    response = client.post(url, data, content_type='application/json')
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert 'Stock insuficiente' in response.json()['error']

@pytest.mark.django_db
def test_solo_cocinero_puede_marcar_listo(client, usuario_cocinero, usuario_mozo, mesa_libre, plato_con_receta):
    # Crear comanda primero
    comanda = Comanda.objects.create(mesa=mesa_libre, mozo=usuario_mozo, codigo_comanda='C1')
    linea = LineaComanda.objects.create(
        comanda=comanda, plato=plato_con_receta, cantidad=1, 
        precio_unitario=15, subtotal=15, estado=LineaComanda.Estado.EN_PREP
    )
    
    url = reverse('api_linea_estado', kwargs={'pk': linea.id})
    
    # Intento mozo (falla)
    client.force_login(usuario_mozo)
    res_mozo = client.patch(url, {'estado': 'LISTO'}, content_type='application/json')
    assert res_mozo.status_code == status.HTTP_403_FORBIDDEN
    
    # Intento cocina (ok)
    client.force_login(usuario_cocinero)
    res_cocina = client.patch(url, {'estado': 'LISTO'}, content_type='application/json')
    assert res_cocina.status_code == status.HTTP_200_OK
    assert LineaComanda.objects.get(pk=linea.id).estado == 'LISTO'


@pytest.mark.django_db
def test_mozo_puede_marcar_pedido_entregado(client, usuario_mozo, mesa_libre, plato_con_receta):
    mesa_libre.estado = Mesa.Estado.OCUPADA
    mesa_libre.save(update_fields=['estado'])

    comanda = Comanda.objects.create(
        mesa=mesa_libre,
        mozo=usuario_mozo,
        codigo_comanda='C2',
        estado=Comanda.Estado.ABIERTA,
    )
    linea = LineaComanda.objects.create(
        comanda=comanda,
        plato=plato_con_receta,
        cantidad=1,
        precio_unitario=15,
        subtotal=15,
        estado=LineaComanda.Estado.LISTO,
    )

    client.force_login(usuario_mozo)
    url = reverse('api_marcar_pedido_entregado', kwargs={'pk': comanda.id})
    response = client.post(url, data={}, content_type='application/json')
    assert response.status_code == status.HTTP_200_OK

    linea.refresh_from_db()
    assert linea.estado == LineaComanda.Estado.ENTREGADO

    estado_url = reverse('api_estado_actual')
    estado_resp = client.get(estado_url)
    assert estado_resp.status_code == status.HTTP_200_OK
    mesa_data = next(m for m in estado_resp.json()['mesas'] if m['id'] == mesa_libre.id)
    assert mesa_data['estado'] == 'ENTREGADO'


@pytest.mark.django_db
def test_marcar_listo_descuenta_stock_real(
    client, usuario_cocinero, mesa_libre, plato_con_receta, insumo_con_stock
):
    comanda = Comanda.objects.create(
        mesa=mesa_libre, mozo=usuario_cocinero, codigo_comanda='C-STK', estado=Comanda.Estado.ABIERTA
    )
    linea = LineaComanda.objects.create(
        comanda=comanda,
        plato=plato_con_receta,
        cantidad=2,
        precio_unitario=15,
        subtotal=30,
        estado=LineaComanda.Estado.EN_PREP,
    )
    real_antes = float(insumo_con_stock.stock_real)
    client.force_login(usuario_cocinero)
    url = reverse('api_linea_estado', kwargs={'pk': linea.id})
    response = client.patch(url, {'estado': 'LISTO'}, content_type='application/json')
    assert response.status_code == status.HTTP_200_OK
    insumo_con_stock.refresh_from_db()
    assert float(insumo_con_stock.stock_real) == real_antes - 1.0
