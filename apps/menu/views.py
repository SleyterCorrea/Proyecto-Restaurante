"""
API endpoint: GET /api/menu/catalogo/
Devuelve el catálogo completo de platos agrupados por categoría.
Solo incluye platos con disponible=True.
"""
import json
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser

from apps.usuarios.permissions import EsAdmin
from apps.usuarios.utils import log_auditoria
from .models import Categoria, Plato
from .serializers import CategoriaSerializer, PlatoSerializer

class CategoriaViewSet(viewsets.ModelViewSet):
    queryset = Categoria.objects.all().order_by('orden', 'nombre')
    serializer_class = CategoriaSerializer
    permission_classes = [IsAuthenticated, EsAdmin]

    def perform_create(self, serializer):
        instance = serializer.save()
        log_auditoria(self.request.user, 'CREACION', 'CATEGORIA', instance.id, 
                      detalle_nuevo=serializer.data, request=self.request)

    def perform_update(self, serializer):
        old_instance = self.get_object()
        old_data = CategoriaSerializer(old_instance).data
        instance = serializer.save()
        log_auditoria(self.request.user, 'EDICION', 'CATEGORIA', instance.id, 
                      detalle_anterior=old_data, detalle_nuevo=serializer.data, request=self.request)

    def perform_destroy(self, instance):
        old_data = CategoriaSerializer(instance).data
        instance_id = instance.id
        instance.delete()
        log_auditoria(self.request.user, 'ELIMINACION', 'CATEGORIA', instance_id, 
                      detalle_anterior=old_data, request=self.request)

class PlatoViewSet(viewsets.ModelViewSet):
    queryset = Plato.objects.all().order_by('categoria__orden', 'nombre')
    serializer_class = PlatoSerializer
    permission_classes = [IsAuthenticated, EsAdmin]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def perform_create(self, serializer):
        instance = serializer.save()
        log_auditoria(self.request.user, 'CREACION', 'PLATOS', instance.id, 
                      detalle_nuevo=serializer.data, request=self.request)

    def perform_update(self, serializer):
        # Obtener detalle anterior
        old_instance = self.get_object()
        old_data = PlatoSerializer(old_instance).data
        instance = serializer.save()
        log_auditoria(self.request.user, 'EDICION', 'PLATOS', instance.id, 
                      detalle_anterior=old_data, detalle_nuevo=serializer.data, request=self.request)

    def perform_destroy(self, instance):
        old_data = PlatoSerializer(instance).data
        instance_id = instance.id
        instance.delete()
        log_auditoria(self.request.user, 'ELIMINACION', 'PLATOS', instance_id, 
                      detalle_anterior=old_data, request=self.request)


@require_GET
def catalogo_api(request):
    """
    Responde con la lista de categorías y sus platos disponibles.
    Formato:
    {
      "categorias": [
        { "id": 1, "nombre": "Entradas", "icono": "bi-egg-fried",
          "platos": [{ "id": 1, "nombre": "...", "precio": "12.50", "imagen": "..." }] }
      ]
    }
    """
    categorias = []
    for cat in Categoria.objects.prefetch_related('platos').all():
        platos_disponibles = cat.platos.filter(disponible=True)
        if platos_disponibles.exists():
            categorias.append({
                'id':     cat.pk,
                'nombre': cat.nombre,
                'icono':  cat.icono,
                'platos': [
                    {
                        'id':          p.pk,
                        'nombre':      p.nombre,
                        'descripcion': p.descripcion,
                        'precio':      str(p.precio),
                        'imagen':      p.imagen_url(),
                        'tiempo_prep': p.tiempo_prep,
                    }
                    for p in platos_disponibles
                ],
            })

    return JsonResponse({'categorias': categorias})
