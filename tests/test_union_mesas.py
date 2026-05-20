import pytest
from django.urls import reverse
from rest_framework import status
from apps.mesas.models import Mesa, Zona
from apps.comandas.models import Comanda

@pytest.fixture
def mesas_libres(db):
    zona, _ = Zona.objects.get_or_create(nombre='Salon')
    m1 = Mesa.objects.create(numero=1, capacidad=4, zona=zona, estado=Mesa.Estado.LIBRE)
    m2 = Mesa.objects.create(numero=2, capacidad=2, zona=zona, estado=Mesa.Estado.LIBRE)
    m3 = Mesa.objects.create(numero=3, capacidad=4, zona=zona, estado=Mesa.Estado.LIBRE)
    m4 = Mesa.objects.create(numero=4, capacidad=4, zona=zona, estado=Mesa.Estado.LIBRE)
    return [m1, m2, m3, m4]

@pytest.mark.django_db
def test_unir_dos_mesas_exito(client, usuario_mozo, mesas_libres, plato_con_receta):
    client.force_login(usuario_mozo)
    m1, m2 = mesas_libres[0], mesas_libres[1]
    
    url = reverse('api_crear_comanda')
    data = {
        'mesa_ids': [m1.id, m2.id],
        'items': [{'plato_id': plato_con_receta.id, 'cantidad': 1}]
    }
    
    response = client.post(url, data, content_type='application/json')
    assert response.status_code == status.HTTP_200_OK
    
    # Verificar que ambas estén OCUPADAS
    m1.refresh_from_db()
    m2.refresh_from_db()
    assert m1.estado == Mesa.Estado.OCUPADA
    assert m2.estado == Mesa.Estado.OCUPADA
    
    # Verificar la comanda
    comanda = Comanda.objects.get(pk=response.json()['comanda_id'])
    assert comanda.mesa == m1
    assert comanda.mesas_adicionales.filter(id=m2.id).exists()
    assert len(comanda.todas_las_mesas) == 2

@pytest.mark.django_db
def test_unir_tres_mesas_limite_maximo(client, usuario_mozo, mesas_libres, plato_con_receta):
    client.force_login(usuario_mozo)
    m1, m2, m3 = mesas_libres[0], mesas_libres[1], mesas_libres[2]
    
    url = reverse('api_crear_comanda')
    data = {
        'mesa_ids': [m1.id, m2.id, m3.id],
        'items': [{'plato_id': plato_con_receta.id, 'cantidad': 1}]
    }
    
    response = client.post(url, data, content_type='application/json')
    assert response.status_code == status.HTTP_200_OK
    assert Comanda.objects.get(pk=response.json()['comanda_id']).mesas_adicionales.count() == 2

@pytest.mark.django_db
def test_error_al_unir_cuatro_mesas(client, usuario_mozo, mesas_libres, plato_con_receta):
    client.force_login(usuario_mozo)
    ids = [m.id for m in mesas_libres] # Son 4
    
    url = reverse('api_crear_comanda')
    data = {
        'mesa_ids': ids,
        'items': [{'plato_id': plato_con_receta.id, 'cantidad': 1}]
    }
    
    response = client.post(url, data, content_type='application/json')
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert 'Máximo 3 mesas' in response.json()['error']

@pytest.mark.django_db
def test_liberacion_grupal_al_cobrar(client, usuario_cajero, usuario_mozo, mesas_libres, plato_con_receta, turno_caja_abierto, metodos_pago):
    client.force_login(usuario_mozo)
    m1, m2 = mesas_libres[0], mesas_libres[1]
    
    # 1. Crear comanda unida
    url_crear = reverse('api_crear_comanda')
    data_crear = {
        'mesa_ids': [m1.id, m2.id],
        'items': [{'plato_id': plato_con_receta.id, 'cantidad': 1}]
    }
    resp_crear = client.post(url_crear, data_crear, content_type='application/json')
    comanda_id = resp_crear.json()['comanda_id']
    
    # 2. Enviar a caja (api_liberar_mesa)
    resp_liberar = client.post(reverse('api_liberar_mesa', kwargs={'mesa_id': m1.id}))
    assert resp_liberar.status_code == 200
    
    # 3. Cobrar en caja
    comanda = Comanda.objects.get(pk=comanda_id)
    comanda.refresh_from_db()
    
    client.force_login(usuario_cajero)
    url_pagar = reverse('api_comanda_pagar', kwargs={'pk': comanda_id})
    data_pagar = {
        'metodo_pago_id': metodos_pago[0].id,
        'monto_recibido': 100
    }
    resp_pagar = client.post(url_pagar, data_pagar, content_type='application/json')
    assert resp_pagar.status_code == status.HTTP_200_OK
    
    # 4. Verificar que AMBAS mesas estén LIBRES
    m1.refresh_from_db()
    m2.refresh_from_db()
    assert m1.estado == Mesa.Estado.LIBRE
    assert m2.estado == Mesa.Estado.LIBRE
