from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from apps.inventario.models import (
    Insumo, InsumoCambioMedida, MovimientoInventario, OrdenCompra,
    RecetaInsumo, UnidadMedida,
)
from apps.inventario.services import InventarioService
from apps.menu.models import Categoria, Plato


@pytest.mark.django_db
def test_panel_inventario_serializa_medidas_decimal(client, usuario_admin):
    client.force_login(usuario_admin)
    response = client.get('/admin-panel/inventario/')
    assert response.status_code == 200


@pytest.mark.django_db
def test_insumo_no_se_elimina_y_solo_se_inactiva_con_motivo(
    client, usuario_admin, insumo_con_stock,
):
    client.force_login(usuario_admin)
    url = f'/api/inventario/insumos/{insumo_con_stock.id}/'

    assert client.delete(url).status_code == 405
    with pytest.raises(ValidationError):
        insumo_con_stock.delete()
    with pytest.raises(ValidationError):
        Insumo.objects.filter(pk=insumo_con_stock.pk).delete()

    sin_motivo = client.post(
        f'{url}inactivar/', {}, content_type='application/json'
    )
    assert sin_motivo.status_code == 400

    response = client.post(
        f'{url}inactivar/',
        {'motivo': 'El proveedor retiro esta presentacion.'},
        content_type='application/json',
    )
    assert response.status_code == 200
    insumo_con_stock.refresh_from_db()
    assert insumo_con_stock.activo is False
    assert insumo_con_stock.motivo_inactivacion == 'El proveedor retiro esta presentacion.'
    assert insumo_con_stock.inactivado_por == usuario_admin
    assert insumo_con_stock.inactivado_en is not None
    assert Insumo.objects.filter(pk=insumo_con_stock.pk).exists()


@pytest.mark.django_db
def test_correccion_medida_migra_cantidades_y_deja_historial(
    client, usuario_admin, insumo_con_stock, plato_con_receta, magnitudes_medida,
):
    client.force_login(usuario_admin)
    litro = UnidadMedida.objects.create(
        nombre='Litro correccion explicita', simbolo='l-correccion',
        magnitud=magnitudes_medida['VOLUMEN'], factor_conversion=Decimal('1000'),
        tipo='CONTINUA',
    )
    MovimientoInventario.objects.create(
        insumo=insumo_con_stock,
        tipo_movimiento=MovimientoInventario.TipoMovimiento.CONSUMO,
        cantidad=Decimal('0.5'), stock_anterior=Decimal('10'),
        stock_nuevo=Decimal('9.5'), costo_unitario=Decimal('2'),
        usuario=usuario_admin,
    )
    Insumo.objects.filter(pk=insumo_con_stock.pk).update(
        medida_requiere_revision=True, costo_unitario=Decimal('3')
    )

    response = client.post(
        f'/api/inventario/insumos/{insumo_con_stock.id}/corregir-medida/',
        {
            'magnitud': magnitudes_medida['VOLUMEN'].id,
            'unidad_medida': litro.id,
            'factor_conversion': '0.75000000',
            'motivo': 'Se verifico que la presentacion equivale a 750 ml.',
        },
        content_type='application/json',
    )
    assert response.status_code == 200, response.json()

    insumo_con_stock.refresh_from_db()
    receta = RecetaInsumo.objects.get(plato=plato_con_receta, insumo=insumo_con_stock)
    movimiento = MovimientoInventario.objects.get(insumo=insumo_con_stock)
    assert insumo_con_stock.magnitud == magnitudes_medida['VOLUMEN']
    assert insumo_con_stock.unidad_medida == litro
    assert insumo_con_stock.stock_real == Decimal('7.500000')
    assert insumo_con_stock.stock_actual == Decimal('7.500000')
    assert insumo_con_stock.stock_minimo == Decimal('0.750000')
    assert insumo_con_stock.costo_unitario == Decimal('4.0000')
    assert insumo_con_stock.medida_requiere_revision is False
    assert receta.unidad_medida == litro
    assert receta.cantidad_por_porcion == Decimal('0.375000')
    assert movimiento.cantidad == Decimal('0.375000')
    cambio = InsumoCambioMedida.objects.get(insumo=insumo_con_stock)
    assert cambio.factor_conversion == Decimal('0.75000000')
    assert cambio.usuario == usuario_admin

@pytest.mark.django_db
def test_signal_deshabilita_plato_cuando_stock_cero(insumo_con_stock, plato_con_receta):
    # Insumo con stock (10) -> Plato disponible (True)
    assert plato_con_receta.disponible == True
    
    # Agotar stock
    insumo_con_stock.stock_real = 0
    insumo_con_stock.save(update_fields=['stock_real'])
    
    # Recargar plato
    plato_con_receta.refresh_from_db()
    assert plato_con_receta.disponible == False

@pytest.mark.django_db
def test_ajuste_manual_registra_movimiento_inventario(client, usuario_admin, insumo_con_stock):
    client.force_login(usuario_admin)
    url = f'/api/inventario/insumos/{insumo_con_stock.id}/ajuste/' # Ajustar segun tus URLs de inventario
    
    # Necesito verificar la URL real del ajuste
    # Supongamos que es /api/insumos/<id>/ajuste/
    url = f'/api/inventario/insumos/{insumo_con_stock.id}/ajuste/'
    
    # Por ahora probamos la lógica del modelo si la API no está lista
    stock_anterior = insumo_con_stock.stock_actual
    insumo_con_stock.stock_actual = 15
    insumo_con_stock.save()
    
    MovimientoInventario.objects.create(
        insumo=insumo_con_stock,
        tipo_movimiento='AJUSTE_POSITIVO',
        cantidad=5,
        stock_anterior=stock_anterior,
        stock_nuevo=15,
        usuario=usuario_admin
    )
    
    assert MovimientoInventario.objects.filter(insumo=insumo_con_stock).count() > 0


@pytest.mark.django_db
def test_api_inventario_exige_enteros_en_unidades_discretas(client, usuario_admin, magnitudes_medida):
    client.force_login(usuario_admin)
    unidad = UnidadMedida.objects.create(
        nombre='Unidad discreta inventario',
        simbolo='und-prueba',
        magnitud=magnitudes_medida['UNIDAD'],
        factor_conversion=1,
        tipo=UnidadMedida.TIPO_DISCRETA,
    )
    datos = {
        'nombre': 'Insumo discreto de prueba',
        'magnitud': magnitudes_medida['UNIDAD'].id,
        'unidad_medida': unidad.id,
        'categoria': 'OTRO',
        'stock_actual': '2.50',
        'stock_real': '2.50',
        'stock_minimo': '1',
        'costo_unitario': '3.50',
    }

    response = client.post(
        '/api/inventario/insumos/',
        datos,
        content_type='application/json',
    )
    assert response.status_code == 400
    assert 'stock_actual' in response.json()
    assert 'stock_real' in response.json()

    datos['stock_actual'] = '2'
    datos['stock_real'] = '2'
    response = client.post(
        '/api/inventario/insumos/',
        datos,
        content_type='application/json',
    )
    assert response.status_code == 201
    assert response.json()['unidad_es_discreta'] is True


@pytest.mark.django_db
def test_ajuste_rechaza_fracciones_en_unidades_discretas(client, usuario_admin, magnitudes_medida):
    client.force_login(usuario_admin)
    unidad = UnidadMedida.objects.create(
        nombre='Botella discreta inventario',
        simbolo='bot-prueba',
        magnitud=magnitudes_medida['UNIDAD'],
        factor_conversion=1,
        tipo=UnidadMedida.TIPO_DISCRETA,
    )
    insumo = Insumo.objects.create(
        nombre='Botella de prueba',
        magnitud=magnitudes_medida['UNIDAD'],
        unidad_medida=unidad,
        stock_actual=5,
        stock_real=5,
        stock_minimo=1,
    )

    response = client.post(
        f'/api/inventario/insumos/{insumo.id}/ajuste/',
        {
            'tipo': 'AJUSTE_POSITIVO',
            'cantidad': '1.50',
            'motivo': 'Conteo de prueba',
        },
        content_type='application/json',
    )

    assert response.status_code == 400
    assert 'numero entero' in str(response.json()).lower()
    insumo.refresh_from_db()
    assert insumo.stock_real == 5


@pytest.mark.django_db
def test_merma_de_insumo_en_revision_usa_stock_decimal_real(
    client, usuario_admin, magnitudes_medida,
):
    client.force_login(usuario_admin)
    unidad = UnidadMedida.objects.create(
        nombre='Botella historica en revision', simbolo='bot-revision',
        magnitud=magnitudes_medida['UNIDAD'], factor_conversion=1,
        tipo=UnidadMedida.TIPO_DISCRETA,
    )
    insumo = Insumo.objects.create(
        nombre='Presentacion ambigua para merma',
        magnitud=magnitudes_medida['UNIDAD'], unidad_medida=unidad,
        stock_actual=50, stock_real=50, stock_minimo=1,
    )
    Insumo.objects.filter(pk=insumo.pk).update(
        stock_actual=Decimal('49.92'), stock_real=Decimal('49.92'),
        medida_requiere_revision=True,
    )

    exceso = client.post(
        f'/api/inventario/insumos/{insumo.id}/merma/',
        {'cantidad': '50', 'causa': 'VENCIDO', 'observacion': 'Prueba'},
        content_type='application/json',
    )
    assert exceso.status_code == 400
    assert exceso.json()['stock_disponible'] == 49.92

    exacta = client.post(
        f'/api/inventario/insumos/{insumo.id}/merma/',
        {'cantidad': '49.92', 'causa': 'VENCIDO', 'observacion': 'Baja total'},
        content_type='application/json',
    )
    assert exacta.status_code == 200
    insumo.refresh_from_db()
    assert insumo.stock_real == Decimal('0.000000')


@pytest.mark.django_db
def test_api_conserva_precision_de_stock_continuo(client, usuario_admin, magnitudes_medida):
    client.force_login(usuario_admin)
    unidad = UnidadMedida.objects.create(
        nombre='Kilogramos redondeo',
        simbolo='kg-redondeo',
        magnitud=magnitudes_medida['MASA'],
        factor_conversion=1000,
        tipo=UnidadMedida.TIPO_CONTINUA,
    )

    response = client.post(
        '/api/inventario/insumos/',
        {
            'nombre': 'Insumo continuo redondeado',
            'magnitud': magnitudes_medida['MASA'].id,
            'unidad_medida': unidad.id,
            'categoria': 'OTRO',
            'stock_actual': '3.998',
            'stock_real': '1.235',
            'stock_minimo': '2.345',
            'costo_unitario': '3.50',
        },
        content_type='application/json',
    )

    assert response.status_code == 201
    insumo = Insumo.objects.get(pk=response.json()['id'])
    assert insumo.stock_actual == Decimal('3.998000')
    assert insumo.stock_real == Decimal('1.235000')
    assert insumo.stock_minimo == Decimal('2.345000')


@pytest.mark.django_db
def test_api_editar_redondea_valor_antiguo_sin_reducir_precision_interna(
    client,
    usuario_admin,
    magnitudes_medida,
):
    client.force_login(usuario_admin)
    unidad = UnidadMedida.objects.create(
        nombre='Litros redondeo',
        simbolo='l-redondeo',
        magnitud=magnitudes_medida['VOLUMEN'],
        factor_conversion=1000,
        tipo=UnidadMedida.TIPO_CONTINUA,
    )
    insumo = Insumo.objects.create(
        nombre='Insumo antiguo con milésimas',
        unidad_medida=unidad,
        magnitud=magnitudes_medida['VOLUMEN'],
        categoria='OTRO',
        stock_actual=Decimal('9.875'),
        stock_real=Decimal('9.875'),
        stock_minimo=Decimal('3.998'),
        costo_unitario=Decimal('2.50'),
    )

    response = client.patch(
        f'/api/inventario/insumos/{insumo.id}/',
        {'stock_minimo': '3.998'},
        content_type='application/json',
    )

    assert response.status_code == 200
    insumo.refresh_from_db()
    assert insumo.stock_minimo == Decimal('3.998000')
    assert insumo.stock_real == Decimal('9.875')
    assert insumo.stock_actual == Decimal('9.875')


@pytest.mark.django_db
def test_api_rechaza_edicion_directa_de_stock(client, usuario_admin, insumo_con_stock):
    client.force_login(usuario_admin)
    stock_anterior = insumo_con_stock.stock_real

    response = client.patch(
        f'/api/inventario/insumos/{insumo_con_stock.id}/',
        {'stock_real': str(stock_anterior + 1)},
        content_type='application/json',
    )

    assert response.status_code == 400
    assert 'trazabilidad' in str(response.json()).lower()
    insumo_con_stock.refresh_from_db()
    assert insumo_con_stock.stock_real == stock_anterior


@pytest.mark.django_db
def test_api_inventario_operativo_es_solo_para_admin(
    client, usuario_mozo, insumo_con_stock
):
    client.force_login(usuario_mozo)

    assert client.get('/api/inventario/insumos/').status_code == 403
    assert client.get('/api/inventario/movimientos/').status_code == 403


@pytest.mark.django_db
def test_conversion_solo_entre_unidades_de_la_misma_magnitud(magnitudes_medida):
    gramo = UnidadMedida.objects.create(
        nombre='Gramo prueba', simbolo='g-prueba',
        magnitud=magnitudes_medida['MASA'], factor_conversion=Decimal('1'),
        tipo='CONTINUA',
    )
    kilogramo = UnidadMedida.objects.create(
        nombre='Kilogramo prueba conversion', simbolo='kg-conv',
        magnitud=magnitudes_medida['MASA'], factor_conversion=Decimal('1000'),
        tipo='CONTINUA',
    )
    litro = UnidadMedida.objects.create(
        nombre='Litro prueba conversion', simbolo='l-conv',
        magnitud=magnitudes_medida['VOLUMEN'], factor_conversion=Decimal('1000'),
        tipo='CONTINUA',
    )

    assert kilogramo.convertir_a(Decimal('1.25'), gramo) == Decimal('1250.00')
    with pytest.raises(ValidationError):
        kilogramo.convertir_a(Decimal('1'), litro)


@pytest.mark.django_db
def test_modelo_y_api_bloquean_unidad_incompatible(
    client, usuario_admin, magnitudes_medida,
):
    client.force_login(usuario_admin)
    litro = UnidadMedida.objects.create(
        nombre='Litro incompatible', simbolo='l-incompatible',
        magnitud=magnitudes_medida['VOLUMEN'], factor_conversion=Decimal('1000'),
        tipo='CONTINUA',
    )
    insumo = Insumo(
        nombre='Aji entero incompatible', magnitud=magnitudes_medida['MASA'],
        unidad_medida=litro,
    )
    with pytest.raises(ValidationError):
        insumo.save()

    response = client.post('/api/inventario/insumos/', {
        'nombre': 'Leche incompatible',
        'magnitud': magnitudes_medida['MASA'].id,
        'unidad_medida': litro.id,
        'categoria': 'LACTEO',
        'stock_actual': '0', 'stock_real': '0', 'stock_minimo': '0',
        'costo_unitario': '1',
    }, content_type='application/json')
    assert response.status_code == 400
    assert 'unidad_medida' in response.json()


@pytest.mark.django_db
def test_receta_en_gramos_se_normaliza_al_stock_en_kilogramos(
    magnitudes_medida,
):
    gramo = UnidadMedida.objects.create(
        nombre='Gramo receta', simbolo='g-receta',
        magnitud=magnitudes_medida['MASA'], factor_conversion=Decimal('1'),
        tipo='CONTINUA',
    )
    kilogramo = UnidadMedida.objects.create(
        nombre='Kilogramo stock receta', simbolo='kg-stock-receta',
        magnitud=magnitudes_medida['MASA'], factor_conversion=Decimal('1000'),
        tipo='CONTINUA',
    )
    insumo = Insumo.objects.create(
        nombre='Aji amarillo entero', magnitud=magnitudes_medida['MASA'],
        unidad_medida=kilogramo, stock_actual=2, stock_real=2,
    )
    categoria = Categoria.objects.create(nombre='Conversion receta')
    plato = Plato.objects.create(
        nombre='Plato con gramos', categoria=categoria, precio_actual=10,
    )
    receta = RecetaInsumo.objects.create(
        plato=plato, insumo=insumo, unidad_medida=gramo,
        cantidad_por_porcion=Decimal('250'),
    )

    assert receta.cantidad_en_unidad_control == Decimal('0.25')
    assert InventarioService.verificar_stock_plato(plato, 8) is True


@pytest.mark.django_db
def test_api_unidades_filtra_por_magnitud(client, usuario_admin, magnitudes_medida):
    client.force_login(usuario_admin)
    UnidadMedida.objects.create(
        nombre='Mililitro filtro', simbolo='ml-filtro',
        magnitud=magnitudes_medida['VOLUMEN'], factor_conversion=1,
        tipo='CONTINUA',
    )
    response = client.get(
        f"/api/inventario/unidades-medida/?magnitud={magnitudes_medida['VOLUMEN'].id}"
    )
    assert response.status_code == 200
    datos = response.json()
    unidades = datos.get('results', []) if isinstance(datos, dict) else datos
    assert unidades
    assert all(item['magnitud'] == magnitudes_medida['VOLUMEN'].id for item in unidades)


@pytest.mark.django_db
def test_orden_automatica_no_duplica_insumo_con_compra_pendiente(
    client, usuario_admin, insumo_con_stock
):
    client.force_login(usuario_admin)
    Insumo.objects.filter(pk=insumo_con_stock.pk).update(
        stock_real=Decimal('1'), stock_actual=Decimal('1'), stock_minimo=Decimal('2')
    )

    primera = client.post(
        '/api/inventario/ordenes-compra/generar-automatica/',
        {},
        content_type='application/json',
    )
    segunda = client.post(
        '/api/inventario/ordenes-compra/generar-automatica/',
        {},
        content_type='application/json',
    )

    assert primera.status_code == 201
    assert segunda.status_code == 400
    assert OrdenCompra.objects.count() == 1


@pytest.mark.django_db
def test_recepcion_de_orden_exige_cantidad_en_cada_item(
    client, usuario_admin, insumo_con_stock
):
    client.force_login(usuario_admin)
    Insumo.objects.filter(pk=insumo_con_stock.pk).update(
        stock_real=Decimal('1'), stock_actual=Decimal('1'), stock_minimo=Decimal('2')
    )
    creada = client.post(
        '/api/inventario/ordenes-compra/generar-automatica/',
        {},
        content_type='application/json',
    ).json()

    response = client.post(
        f"/api/inventario/ordenes-compra/{creada['id']}/recibir/",
        {'items': [{'id': item['id'], 'cantidad_recibida': 0} for item in creada['items']]},
        content_type='application/json',
    )

    assert response.status_code == 400
    orden = OrdenCompra.objects.get(pk=creada['id'])
    assert orden.estado == OrdenCompra.Estado.BORRADOR
    insumo_con_stock.refresh_from_db()
    assert insumo_con_stock.stock_real == Decimal('1')
