import pytest
from django.urls import reverse
from rest_framework import status

@pytest.mark.django_db
def test_mozo_no_puede_acceder_kds(client, usuario_mozo):
    client.force_login(usuario_mozo)
    url = '/cocina/kds/'
    response = client.get(url)
    # Redirige a /mesero/mesas/ por el decorador @rol_requerido
    assert response.status_code == 302
    assert response.url == '/mesero/mesas/'

@pytest.mark.django_db
def test_cocinero_no_puede_crear_comanda(client, usuario_cocinero):
    client.force_login(usuario_cocinero)
    url = reverse('api_crear_comanda')
    response = client.post(url, {}, content_type='application/json')
    assert response.status_code == status.HTTP_403_FORBIDDEN

@pytest.mark.django_db
def test_admin_puede_acceder_todo(client, usuario_admin):
    client.force_login(usuario_admin)
    urls = ['/mesero/mesas/', '/cocina/kds/', '/admin-panel/dashboard/']
    for url in urls:
        response = client.get(url)
        assert response.status_code == 200
