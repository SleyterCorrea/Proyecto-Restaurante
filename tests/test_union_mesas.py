import pytest
from django.urls import reverse
from rest_framework import status

from apps.comandas.models import Comanda, LineaComanda
from apps.mesas.models import Mesa, UnionMesas, Zona


@pytest.fixture
def mesas_libres(db):
    zona, _ = Zona.objects.get_or_create(nombre='Salon')
    m1 = Mesa.objects.create(numero=1, capacidad=4, zona=zona, estado=Mesa.Estado.LIBRE)
    m2 = Mesa.objects.create(numero=2, capacidad=2, zona=zona, estado=Mesa.Estado.LIBRE)
    m3 = Mesa.objects.create(numero=3, capacidad=4, zona=zona, estado=Mesa.Estado.LIBRE)
    m4 = Mesa.objects.create(numero=4, capacidad=4, zona=zona, estado=Mesa.Estado.LIBRE)
    return [m1, m2, m3, m4]


def crear_union(mesas, capacidad=None):
    union = UnionMesas.objects.create(
        mesa_principal=mesas[0],
        capacidad_personalizada=capacidad,
    )
    union.mesas_secundarias.set(mesas[1:])
    return union


@pytest.mark.django_db
def test_crear_comanda_para_union_de_dos_mesas(client, usuario_mozo, mesas_libres, plato_con_receta):
    client.force_login(usuario_mozo)
    m1, m2 = mesas_libres[0], mesas_libres[1]
    union = crear_union([m1, m2])

    response = client.post(reverse('api_crear_comanda'), {
        'mesa_id': m1.id,
        'union_id': union.id,
        'items': [{'plato_id': plato_con_receta.id, 'cantidad': 1}],
    }, content_type='application/json')

    assert response.status_code == status.HTTP_200_OK
    m1.refresh_from_db()
    m2.refresh_from_db()
    assert m1.estado == Mesa.Estado.OCUPADA
    assert m2.estado == Mesa.Estado.OCUPADA

    comanda = Comanda.objects.get(pk=response.json()['comanda_id'])
    assert comanda.mesa == m1
    assert comanda.mesas_adicionales.filter(id=m2.id).exists()
    assert comanda.mesa_label == 'Mesa 1 + 2'


@pytest.mark.django_db
def test_crear_comanda_para_union_de_tres_mesas(client, usuario_mozo, mesas_libres, plato_con_receta):
    client.force_login(usuario_mozo)
    m1, m2, m3 = mesas_libres[0], mesas_libres[1], mesas_libres[2]
    union = crear_union([m1, m2, m3])

    response = client.post(reverse('api_crear_comanda'), {
        'mesa_id': m1.id,
        'union_id': union.id,
        'items': [{'plato_id': plato_con_receta.id, 'cantidad': 1}],
    }, content_type='application/json')

    assert response.status_code == status.HTTP_200_OK
    comanda = Comanda.objects.get(pk=response.json()['comanda_id'])
    assert comanda.mesas_adicionales.count() == 2
    assert comanda.mesa_label == 'Mesa 1 + 2 + 3'


@pytest.mark.django_db
def test_no_permite_comanda_con_mesas_independientes(client, usuario_mozo, mesas_libres, plato_con_receta):
    client.force_login(usuario_mozo)
    m1, m2 = mesas_libres[0], mesas_libres[1]

    response = client.post(reverse('api_crear_comanda'), {
        'mesa_ids': [m1.id, m2.id],
        'items': [{'plato_id': plato_con_receta.id, 'cantidad': 1}],
    }, content_type='application/json')

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert 'una sola mesa' in response.json()['error']


@pytest.mark.django_db
def test_error_al_enviar_cuatro_mesas(client, usuario_mozo, mesas_libres, plato_con_receta):
    client.force_login(usuario_mozo)

    response = client.post(reverse('api_crear_comanda'), {
        'mesa_ids': [m.id for m in mesas_libres],
        'items': [{'plato_id': plato_con_receta.id, 'cantidad': 1}],
    }, content_type='application/json')

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert '3 mesas' in response.json()['error']


@pytest.mark.django_db
def test_union_bloquea_zonas_distintas(client, usuario_mozo):
    zona1 = Zona.objects.create(nombre='Salon A')
    zona2 = Zona.objects.create(nombre='Salon B')
    m1 = Mesa.objects.create(numero=1, capacidad=4, zona=zona1, estado=Mesa.Estado.LIBRE)
    m2 = Mesa.objects.create(numero=2, capacidad=4, zona=zona2, estado=Mesa.Estado.LIBRE)
    client.force_login(usuario_mozo)

    response = client.post(reverse('api_union_crear'), {
        'mesa_principal_id': m1.id,
        'mesa_secundaria_ids': [m2.id],
    }, content_type='application/json')

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert 'misma zona' in response.json()['error']


@pytest.mark.django_db
def test_union_aparece_como_unidad_en_mesas_libres(client, usuario_mozo, mesas_libres):
    m1, m2 = mesas_libres[0], mesas_libres[1]
    union = crear_union([m1, m2], capacidad=7)
    client.force_login(usuario_mozo)

    response = client.get(reverse('api_mesas_libres'))
    assert response.status_code == status.HTTP_200_OK
    mesas = [mesa for grupo in response.json()['pisos'].values() for mesa in grupo]
    grupo = next(mesa for mesa in mesas if mesa.get('union_id') == union.id)

    assert grupo['es_grupo'] is True
    assert grupo['mesa_ids'] == [m1.id, m2.id]
    assert grupo['label'] == 'Mesa 1 + Mesa 2'
    assert len([mesa for mesa in mesas if mesa['id'] in [m1.id, m2.id]]) == 1


@pytest.mark.django_db
def test_zval_no_aparece_en_filtros_ni_api(client, usuario_mozo):
    zval = Zona.objects.create(nombre='ZVAL', activo=True)
    Mesa.objects.create(numero=99, capacidad=4, zona=zval, estado=Mesa.Estado.LIBRE)
    client.force_login(usuario_mozo)

    libres = client.get(reverse('api_mesas_libres')).json()
    estado = client.get(reverse('api_estado_actual')).json()

    assert 'ZVAL' not in libres['pisos']
    assert all(mesa['piso_label'] != 'ZVAL' for mesa in estado['mesas'])


@pytest.mark.django_db
def test_plano_muestra_lineas_en_preparacion_y_estado_kds(
    client, usuario_mozo, usuario_cocinero, mesas_libres, plato_con_receta
):
    client.force_login(usuario_mozo)
    response = client.post(reverse('api_crear_comanda'), {
        'mesa_id': mesas_libres[0].id,
        'items': [{'plato_id': plato_con_receta.id, 'cantidad': 2, 'notas': 'Sin cebolla'}],
    }, content_type='application/json')
    comanda = Comanda.objects.get(pk=response.json()['comanda_id'])
    linea = comanda.lineas.get()

    client.force_login(usuario_cocinero)
    kds_response = client.patch(
        reverse('api_cocina_cambiar_estado', kwargs={'pk': linea.id}),
        {'nuevo_estado': LineaComanda.Estado.EN_PREP},
        content_type='application/json',
    )
    assert kds_response.status_code == status.HTTP_200_OK

    client.force_login(usuario_mozo)
    estado = client.get(reverse('api_estado_actual')).json()
    mesa_data = next(m for m in estado['mesas'] if m['id'] == mesas_libres[0].id)

    assert mesa_data['comanda']['lineas'][0]['cantidad'] == 2
    assert mesa_data['comanda']['lineas'][0]['estado'] == LineaComanda.Estado.EN_PREP
    assert mesa_data['comanda']['lineas'][0]['notas_cocina'] == 'Sin cebolla'


@pytest.mark.django_db
def test_kds_muestra_nombre_completo_de_union(
    client, usuario_mozo, usuario_cocinero, mesas_libres, plato_con_receta
):
    m1, m2 = mesas_libres[0], mesas_libres[1]
    union = crear_union([m1, m2])
    client.force_login(usuario_mozo)
    client.post(reverse('api_crear_comanda'), {
        'mesa_id': m1.id,
        'union_id': union.id,
        'items': [{'plato_id': plato_con_receta.id, 'cantidad': 1}],
    }, content_type='application/json')

    client.force_login(usuario_cocinero)
    response = client.get(reverse('api_cocina_activas'))

    assert response.status_code == status.HTTP_200_OK
    assert response.json()[0]['mesa_label'] == 'Mesa 1 + 2'


@pytest.mark.django_db
def test_liberacion_grupal_al_cobrar(
    client, usuario_cajero, usuario_mozo, mesas_libres, plato_con_receta, turno_caja_abierto, metodos_pago
):
    client.force_login(usuario_mozo)
    m1, m2 = mesas_libres[0], mesas_libres[1]
    union = crear_union([m1, m2])

    resp_crear = client.post(reverse('api_crear_comanda'), {
        'mesa_id': m1.id,
        'union_id': union.id,
        'items': [{'plato_id': plato_con_receta.id, 'cantidad': 1}],
    }, content_type='application/json')
    comanda_id = resp_crear.json()['comanda_id']
    comanda = Comanda.objects.get(pk=comanda_id)
    comanda.lineas.update(estado=LineaComanda.Estado.LISTO)

    resp_liberar = client.post(reverse('api_liberar_mesa', kwargs={'mesa_id': m1.id}))
    assert resp_liberar.status_code == status.HTTP_200_OK

    client.force_login(usuario_cajero)
    resp_pagar = client.post(reverse('api_comanda_pagar', kwargs={'pk': comanda_id}), {
        'metodo_pago_id': metodos_pago[0].id,
        'monto_recibido': 100,
    }, content_type='application/json')
    assert resp_pagar.status_code == status.HTTP_200_OK

    m1.refresh_from_db()
    m2.refresh_from_db()
    assert m1.estado == Mesa.Estado.LIMPIEZA
    assert m2.estado == Mesa.Estado.LIMPIEZA
