"""
Script de datos de prueba para el Sistema de Gestión de Restaurantes.

Ejecutar desde la raíz del proyecto:
    python manage.py shell < seed_data.py
"""
import django
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'restaurant.settings')

from apps.menu.models import Categoria, Plato
from apps.mesas.models import Mesa

print("🌱 Sembrando datos de prueba...")

# ── Categorías ──────────────────────────────────────────────────────────
categorias_data = [
    {'nombre': 'Entradas',  'icono': 'bi-egg-fried',      'orden': 1},
    {'nombre': 'Sopas',     'icono': 'bi-cup-hot',         'orden': 2},
    {'nombre': 'Fondos',    'icono': 'bi-basket2',         'orden': 3},
    {'nombre': 'Postres',   'icono': 'bi-cake2',           'orden': 4},
    {'nombre': 'Bebidas',   'icono': 'bi-cup-straw',       'orden': 5},
]
for cd in categorias_data:
    Categoria.objects.get_or_create(nombre=cd['nombre'], defaults=cd)

cat = {c.nombre: c for c in Categoria.objects.all()}

# ── Platos ──────────────────────────────────────────────────────────────
platos_data = [
    # Entradas
    {'categoria': cat['Entradas'], 'nombre': 'Ceviche Clásico',    'precio': 18.50, 'tiempo_prep': 10},
    {'categoria': cat['Entradas'], 'nombre': 'Causa Rellena',      'precio': 14.00, 'tiempo_prep': 8},
    {'categoria': cat['Entradas'], 'nombre': 'Tequeños',           'precio': 12.00, 'tiempo_prep': 12},
    # Sopas
    {'categoria': cat['Sopas'],    'nombre': 'Sopa de Tomate',     'precio': 10.00, 'tiempo_prep': 15},
    {'categoria': cat['Sopas'],    'nombre': 'Crema de Zapallo',   'precio': 11.50, 'tiempo_prep': 15},
    # Fondos
    {'categoria': cat['Fondos'],   'nombre': 'Lomo Saltado',       'precio': 28.00, 'tiempo_prep': 20},
    {'categoria': cat['Fondos'],   'nombre': 'Pollo a la Brasa',   'precio': 22.00, 'tiempo_prep': 25},
    {'categoria': cat['Fondos'],   'nombre': 'Pasta Carbonara',    'precio': 19.50, 'tiempo_prep': 18},
    {'categoria': cat['Fondos'],   'nombre': 'Trucha al Vapor',    'precio': 32.00, 'tiempo_prep': 22},
    # Postres
    {'categoria': cat['Postres'],  'nombre': 'Suspiro Limeño',     'precio': 9.00,  'tiempo_prep': 5},
    {'categoria': cat['Postres'],  'nombre': 'Brownie con Helado', 'precio': 11.00, 'tiempo_prep': 8},
    # Bebidas
    {'categoria': cat['Bebidas'],  'nombre': 'Limonada Frozen',    'precio': 7.50,  'tiempo_prep': 5},
    {'categoria': cat['Bebidas'],  'nombre': 'Chicha Morada',      'precio': 6.00,  'tiempo_prep': 3},
    {'categoria': cat['Bebidas'],  'nombre': 'Agua Mineral',       'precio': 4.00,  'tiempo_prep': 1},
]
for pd in platos_data:
    Plato.objects.get_or_create(
        nombre=pd['nombre'],
        defaults={**pd, 'disponible': True, 'descripcion': ''}
    )

# ── Mesas ────────────────────────────────────────────────────────────────
mesas_data = [
    # Planta Baja
    *[{'numero': i, 'piso': 'PB', 'capacidad': 4} for i in range(1, 9)],
    # Piso 1
    *[{'numero': i, 'piso': 'P1', 'capacidad': 6} for i in range(9, 15)],
    # Terraza
    *[{'numero': i, 'piso': 'TR', 'capacidad': 2} for i in range(15, 19)],
]
for md in mesas_data:
    Mesa.objects.get_or_create(
        numero=md['numero'],
        defaults={**md, 'estado': Mesa.Estado.LIBRE}
    )

print(f"✅ {Categoria.objects.count()} categorías")
print(f"✅ {Plato.objects.count()} platos")
print(f"✅ {Mesa.objects.count()} mesas")
print("🎉 ¡Datos listos! Corre: python manage.py runserver")
