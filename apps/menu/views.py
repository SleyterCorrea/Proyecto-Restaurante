"""
API endpoint: GET /api/menu/catalogo/
Devuelve el catálogo completo de platos agrupados por categoría.
Solo incluye platos con disponible=True.
"""
import json
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from .models import Categoria, Plato


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
