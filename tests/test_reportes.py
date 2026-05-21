import pytest
from django.urls import reverse
from rest_framework import status
from apps.caja.models import CajaTurno, Pago, MetodoPago
from apps.comandas.models import Comanda, LineaComanda
from apps.menu.models import Plato, Categoria
from django.contrib.auth import get_user_model

User = get_user_model()

@pytest.fixture
def setup_data(db):
    from apps.usuarios.models import Rol
    rol_admin, _ = Rol.objects.get_or_create(nombre='ADMIN', defaults={'descripcion': 'Administrador'})
    
    # Crear usuario con rol
    user = User.objects.create_user(
        username='admin_test', 
        password='password123', 
        email='test@test.com',
        rol=rol_admin
    )

    # Crear categoria y plato
    cat = Categoria.objects.create(nombre='Test Cat')
    plato = Plato.objects.create(nombre='Ceviche', precio_actual=50, categoria=cat)
    
    # Metodo de pago
    metodo = MetodoPago.objects.create(codigo='EFECTIVO', nombre='Efectivo')
    
    return user, plato, metodo

@pytest.mark.django_db
def test_api_ventas_turno_trends(client, setup_data):
    user, plato, metodo = setup_data
    client.login(username='admin_test', password='password123')

    from apps.mesas.models import Mesa, Zona
    zona = Zona.objects.create(nombre='Zona Principal')
    mesa1 = Mesa.objects.create(numero=1, capacidad=4, zona=zona)
    mesa2 = Mesa.objects.create(numero=2, capacidad=4, zona=zona)

    # 1. Crear turno anterior cerrado
    turno_ant = CajaTurno.objects.create(
        codigo_turno='TUR-ANT',
        cajero=user,
        saldo_inicial=100,
        total_ventas=100,
        estado=CajaTurno.Estado.CERRADA
    )
    # Crear un pago para el turno anterior
    comanda_ant = Comanda.objects.create(codigo_comanda='C-ANT', mesa=mesa1, mozo=user, total=100, estado=Comanda.Estado.COBRADA)
    Pago.objects.create(caja_turno=turno_ant, comanda=comanda_ant, metodo_pago=metodo, monto=100)

    # 2. Crear turno actual abierto
    turno_act = CajaTurno.objects.create(
        codigo_turno='TUR-ACT',
        cajero=user,
        saldo_inicial=100,
        total_ventas=150,
        estado=CajaTurno.Estado.ABIERTA
    )
    # Crear un pago para el turno actual
    comanda_act = Comanda.objects.create(codigo_comanda='C-ACT', mesa=mesa2, mozo=user, total=150, estado=Comanda.Estado.COBRADA)
    Pago.objects.create(caja_turno=turno_act, comanda=comanda_act, metodo_pago=metodo, monto=150)

    url = reverse('api_ventas_turno')
    response = client.get(url)
    
    assert response.status_code == status.HTTP_200_OK
    data = response.data
    
    # Tendencia ventas: (150 - 100) / 100 * 100 = 50%
    assert data['tendencia_ventas'] == 50.0
    # Tendencia comandas: (1 - 1) / 1 * 100 = 0%
    assert data['tendencia_comandas'] == 0.0

@pytest.mark.django_db
def test_api_ventas_historial_search(client, setup_data):
    user, plato, metodo = setup_data
    client.login(username='admin_test', password='password123')

    turno = CajaTurno.objects.create(
        codigo_turno='TUR-SEARCH',
        cajero=user,
        saldo_inicial=100,
        estado=CajaTurno.Estado.ABIERTA
    )
    
    from apps.mesas.models import Mesa, Zona
    zona = Zona.objects.create(nombre='Planta Baja')
    mesa5 = Mesa.objects.create(numero=5, capacidad=4, zona=zona)
    mesa10 = Mesa.objects.create(numero=10, capacidad=4, zona=zona)

    c1 = Comanda.objects.create(codigo_comanda='ORD-101', mesa=mesa5, mozo=user, total=50, estado=Comanda.Estado.COBRADA)
    LineaComanda.objects.create(comanda=c1, plato=plato, cantidad=1, precio_unitario=50, subtotal=50)
    Pago.objects.create(caja_turno=turno, comanda=c1, metodo_pago=metodo, monto=50)

    c2 = Comanda.objects.create(codigo_comanda='ORD-202', mesa=mesa10, mozo=user, total=100, estado=Comanda.Estado.COBRADA)
    LineaComanda.objects.create(comanda=c2, plato=plato, cantidad=2, precio_unitario=50, subtotal=100)
    Pago.objects.create(caja_turno=turno, comanda=c2, metodo_pago=metodo, monto=100)

    url = reverse('api_ventas_historial')
    
    # Sin busqueda
    res = client.get(url)
    assert len(res.data['results']) == 2
    
    # Busqueda por codigo
    res = client.get(url + '?search=101')
    assert len(res.data['results']) == 1
    assert res.data['results'][0]['codigo'] == 'ORD-101'
    
    # Busqueda por mesa
    res = client.get(url + '?search=10')
    assert len(res.data['results']) == 1
    assert res.data['results'][0]['mesa'] == '10'
