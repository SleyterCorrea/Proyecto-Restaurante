import json

import pytest

from apps.auditoria.models import AuditLog
from apps.inventario.models import Insumo, RecetaInsumo, UnidadMedida


@pytest.mark.django_db
def test_actualizar_datos_generales_menores_no_exige_motivo_y_audita(
    client,
    usuario_admin,
    plato_con_receta,
):
    client.force_login(usuario_admin)
    url = f'/api/menu/platos/{plato_con_receta.id}/'

    response = client.patch(
        url,
        {'descripcion': 'Nueva descripcion'},
        content_type='application/json',
    )

    assert response.status_code == 200
    plato_con_receta.refresh_from_db()
    assert plato_con_receta.descripcion == 'Nueva descripcion'
    log = AuditLog.objects.get(
        accion='PLATO_MODIFICADO',
        entidad_id=plato_con_receta.id,
    )
    assert log.motivo in (None, '')
    assert log.detalle_anterior['descripcion'] == ''
    assert log.detalle_nuevo['descripcion'] == 'Nueva descripcion'


@pytest.mark.django_db
def test_receta_exige_enteros_para_unidades_discretas(
    client,
    usuario_admin,
    plato_con_receta,
    magnitudes_medida,
):
    client.force_login(usuario_admin)
    unidad = UnidadMedida.objects.create(
        nombre='Unidad discreta de prueba',
        simbolo='und-menu',
        magnitud=magnitudes_medida['UNIDAD'],
        factor_conversion=1,
        tipo=UnidadMedida.TIPO_DISCRETA,
    )
    insumo = Insumo.objects.create(
        nombre='Bebida individual de prueba',
        stock_actual=10,
        stock_real=10,
        stock_minimo=1,
        magnitud=magnitudes_medida['UNIDAD'],
        unidad_medida=unidad,
    )
    url = f'/api/menu/platos/{plato_con_receta.id}/'
    receta = [{
        'insumo_id': insumo.id,
        'cantidad_por_porcion': '1.50',
        'merma_porcentaje': '0',
        'activo': True,
    }]

    response = client.patch(
        url,
        {
            'receta_json': json.dumps(receta),
            'motivo': 'Se agrega una bebida por plato.',
        },
        content_type='application/json',
    )

    assert response.status_code == 400
    assert 'entero' in str(response.json()).lower()

    receta[0]['cantidad_por_porcion'] = '2'
    response = client.patch(
        url,
        {
            'receta_json': json.dumps(receta),
            'motivo': 'Se agregan dos bebidas por plato.',
        },
        content_type='application/json',
    )

    assert response.status_code == 200
    assert response.json()['receta'][0]['insumo_es_discreto'] is True
    assert response.json()['receta'][0]['cantidad_por_porcion'] == '2.000000'


@pytest.mark.django_db
def test_editar_receta_json_reemplaza_y_permite_vaciar_receta(
    client,
    usuario_admin,
    plato_con_receta,
    insumo_con_stock,
):
    client.force_login(usuario_admin)
    nuevo_insumo = Insumo.objects.create(
        nombre='Aceite para receta',
        stock_actual=20,
        stock_real=20,
        stock_minimo=1,
        magnitud=insumo_con_stock.magnitud,
        unidad_medida=insumo_con_stock.unidad_medida,
    )
    url = f'/api/menu/platos/{plato_con_receta.id}/'

    response = client.patch(
        url,
        {
            'receta_json': json.dumps([
                {
                    'insumo_id': nuevo_insumo.id,
                    'cantidad_por_porcion': '0.25',
                    'merma_porcentaje': '2.00',
                    'activo': True,
                },
            ]),
            'motivo': 'Se reemplazo el ingrediente principal.',
        },
        content_type='application/json',
    )

    assert response.status_code == 200
    assert [item['insumo_id'] for item in response.json()['receta']] == [nuevo_insumo.id]
    assert not RecetaInsumo.objects.get(
        plato=plato_con_receta,
        insumo=insumo_con_stock,
    ).activo
    assert RecetaInsumo.objects.get(
        plato=plato_con_receta,
        insumo=nuevo_insumo,
    ).activo

    response = client.patch(
        url,
        {
            'disponible': False,
            'receta_json': '[]',
            'motivo': 'El plato queda en revision sin receta activa.',
        },
        content_type='application/json',
    )

    assert response.status_code == 200
    assert response.json()['receta'] == []
    assert not RecetaInsumo.objects.filter(
        plato=plato_con_receta,
        activo=True,
    ).exists()


@pytest.mark.django_db
def test_retirar_plato_es_baja_logica_auditada_y_desaparece_del_listado(
    client,
    usuario_admin,
    plato_con_receta,
):
    client.force_login(usuario_admin)
    url = f'/api/menu/platos/{plato_con_receta.id}/'

    response = client.delete(
        url,
        {'motivo': 'El plato salio de la carta de temporada.'},
        content_type='application/json',
    )

    assert response.status_code == 204
    plato_con_receta.refresh_from_db()
    assert plato_con_receta.activo is False
    assert plato_con_receta.disponible is False
    assert not plato_con_receta.receta.filter(activo=True).exists()

    response = client.get('/api/menu/platos/')
    assert response.status_code == 200
    resultados = response.json()
    if isinstance(resultados, dict):
        resultados = resultados.get('results', [])
    assert plato_con_receta.id not in {item['id'] for item in resultados}

    log = AuditLog.objects.get(
        accion='PLATO_SOFT_DELETE',
        entidad_id=plato_con_receta.id,
    )
    assert log.motivo == 'El plato salio de la carta de temporada.'
