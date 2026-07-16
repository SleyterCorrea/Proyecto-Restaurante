import pytest
import django.template.context
from copy import copy

def patched_copy(self):
    duplicate = self.__class__.__new__(self.__class__)
    for k, v in self.__dict__.items():
        if k != 'dicts':
            duplicate.__dict__[k] = copy(v)
    duplicate.dicts = self.dicts[:]
    return duplicate

django.template.context.BaseContext.__copy__ = patched_copy

from django.contrib.auth import get_user_model
from apps.usuarios.models import Rol
from apps.mesas.models import Mesa, Zona
from apps.menu.models import Plato, Categoria
from apps.comandas.models import Comanda, LineaComanda
from apps.caja.models import CajaTurno, MetodoPago
from apps.inventario.models import Insumo, MagnitudMedida, UnidadMedida, RecetaInsumo

Usuario = get_user_model()

@pytest.fixture
def db_roles(db):
    roles = ['ADMIN', 'MOZO', 'COCINERO', 'CAJERO']
    return {r: Rol.objects.get_or_create(nombre=r)[0] for r in roles}

@pytest.fixture
def usuario_admin(db, db_roles):
    return Usuario.objects.create_superuser(
        username='admin', email='admin@test.com', password='pass123', 
        rol=db_roles['ADMIN'], nombres='Admin', apellidos='Test'
    )

@pytest.fixture
def usuario_mozo(db, db_roles):
    return Usuario.objects.create_user(
        username='mozo1', email='mozo@test.com', password='pass123', 
        rol=db_roles['MOZO'], nombres='Mozo', apellidos='Test'
    )

@pytest.fixture
def usuario_cocinero(db, db_roles):
    return Usuario.objects.create_user(
        username='cocina1', email='cocina@test.com', password='pass123', 
        rol=db_roles['COCINERO'], nombres='Cocinero', apellidos='Test'
    )

@pytest.fixture
def usuario_cajero(db, db_roles):
    return Usuario.objects.create_user(
        username='caja1', email='caja@test.com', password='pass123', 
        rol=db_roles['CAJERO'], nombres='Cajero', apellidos='Test'
    )

@pytest.fixture
def mesa_libre(db):
    zona, _ = Zona.objects.get_or_create(nombre='Salon')
    return Mesa.objects.create(numero=1, capacidad=4, zona=zona, estado=Mesa.Estado.LIBRE)

@pytest.fixture
def magnitudes_medida(db):
    return {
        codigo: MagnitudMedida.objects.get_or_create(codigo=codigo, defaults={'nombre': nombre})[0]
        for codigo, nombre in (('MASA', 'Masa'), ('VOLUMEN', 'Volumen'), ('UNIDAD', 'Unidad'))
    }


@pytest.fixture
def insumo_con_stock(db, magnitudes_medida):
    um, _ = UnidadMedida.objects.get_or_create(
        simbolo='kg',
        defaults={
            'nombre': 'Kilogramo', 'magnitud': magnitudes_medida['MASA'],
            'factor_conversion': 1000, 'tipo': 'CONTINUA',
        },
    )
    return Insumo.objects.create(
        nombre='Papa', stock_actual=10, stock_real=10, stock_minimo=1,
        magnitud=magnitudes_medida['MASA'], unidad_medida=um
    )

@pytest.fixture
def plato_con_receta(db, insumo_con_stock):
    cat, _ = Categoria.objects.get_or_create(nombre='Entradas')
    plato = Plato.objects.create(nombre='Papa a la huancaina', precio_actual=15, categoria=cat, disponible=True)
    RecetaInsumo.objects.create(
        plato=plato, insumo=insumo_con_stock,
        unidad_medida=insumo_con_stock.unidad_medida,
        cantidad_por_porcion=0.5,
    )
    return plato

@pytest.fixture
def turno_caja_abierto(db, usuario_cajero):
    return CajaTurno.objects.create(
        codigo_turno='TUR-TEST',
        cajero=usuario_cajero,
        saldo_inicial=100,
        estado=CajaTurno.Estado.ABIERTA
    )

@pytest.fixture
def metodos_pago(db):
    MetodoPago.objects.get_or_create(codigo='EFECTIVO', nombre='Efectivo', permite_vuelto=True)
    MetodoPago.objects.get_or_create(codigo='TARJETA', nombre='Tarjeta', permite_vuelto=False)
    return MetodoPago.objects.all()
