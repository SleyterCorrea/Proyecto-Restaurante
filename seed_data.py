"""
Script de datos de prueba para RestaurantOS - Versión PostgreSQL.
"""
import django
import os
from django.utils import timezone

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'restaurant.settings')
django.setup()

from apps.usuarios.models import Rol, Usuario
from apps.mesas.models import Zona, Mesa
from apps.menu.models import Categoria, Plato
from apps.inventario.models import UnidadMedida
from apps.caja.models import MetodoPago

print("🌱 Sembrando datos de prueba para PostgreSQL...")

# ── 1. Roles ─────────────────────────────────────────────────────────────
roles_data = [
    {'nombre': 'ADMIN',    'descripcion': 'Administrador del sistema'},
    {'nombre': 'MOZO',     'descripcion': 'Personal de salón'},
    {'nombre': 'COCINERO', 'descripcion': 'Personal de cocina'},
    {'nombre': 'CAJERO',   'descripcion': 'Personal de caja'},
]
for rd in roles_data:
    Rol.objects.get_or_create(nombre=rd['nombre'], defaults=rd)

roles = {r.nombre: r for r in Rol.objects.all()}

# ── 2. Usuarios ──────────────────────────────────────────────────────────
usuarios_data = [
    {'username': 'admin',    'rol': roles['ADMIN'],    'nombres': 'Admin',    'apellidos': 'Principal', 'email': 'admin@restaurant.com'},
    {'username': 'mozo1',    'rol': roles['MOZO'],     'nombres': 'Juan',     'apellidos': 'Perez',     'email': 'mozo1@restaurant.com'},
    {'username': 'cocina1',  'rol': roles['COCINERO'], 'nombres': 'Chef',     'apellidos': 'Gourmet',   'email': 'chef@restaurant.com'},
    {'username': 'caja1',    'rol': roles['CAJERO'],   'nombres': 'Maria',    'apellidos': 'Cajera',    'email': 'caja1@restaurant.com'},
]
for ud in usuarios_data:
    user, created = Usuario.objects.get_or_create(
        username=ud['username'],
        defaults={**ud, 'is_staff': True}
    )
    if created:
        user.set_password('pass123')
        user.save()

# ── 3. Zonas ─────────────────────────────────────────────────────────────
zonas_data = [
    {'nombre': 'Planta Baja', 'descripcion': 'Salón principal entrada'},
    {'nombre': 'Piso 1',      'descripcion': 'Segundo nivel'},
    {'nombre': 'Terraza',     'descripcion': 'Área libre'},
]
for zd in zonas_data:
    Zona.objects.get_or_create(nombre=zd['nombre'], defaults=zd)

zonas = {z.nombre: z for z in Zona.objects.all()}

# ── 4. Mesas ─────────────────────────────────────────────────────────────
mesas_data = [
    # Planta Baja (1-8)
    *[{'numero': i, 'zona': zonas['Planta Baja'], 'capacidad': 4} for i in range(1, 9)],
    # Piso 1 (9-14)
    *[{'numero': i, 'zona': zonas['Piso 1'],      'capacidad': 6} for i in range(9, 15)],
    # Terraza (15-18)
    *[{'numero': i, 'zona': zonas['Terraza'],     'capacidad': 2} for i in range(15, 19)],
]
for md in mesas_data:
    Mesa.objects.get_or_create(
        numero=md['numero'],
        zona=md['zona'],
        defaults={'capacidad': md['capacidad'], 'estado': Mesa.Estado.LIBRE}
    )

# ── 5. Categorías y Platos ───────────────────────────────────────────────
categorias_data = [
    {'nombre': 'Entradas',  'icono': 'bi-egg-fried', 'orden': 1},
    {'nombre': 'Fondos',    'icono': 'bi-basket2',    'orden': 2},
    {'nombre': 'Postres',   'icono': 'bi-cake2',      'orden': 3},
    {'nombre': 'Bebidas',   'icono': 'bi-cup-straw',  'orden': 4},
]
for cd in categorias_data:
    Categoria.objects.get_or_create(nombre=cd['nombre'], defaults=cd)

cat = {c.nombre: c for c in Categoria.objects.all()}

platos_data = [
    {'categoria': cat['Entradas'], 'nombre': 'Ceviche',       'precio_actual': 25.00, 'tiempo_preparacion_min': 10},
    {'categoria': cat['Entradas'], 'nombre': 'Tequeños',      'precio_actual': 15.00, 'tiempo_preparacion_min': 12},
    {'categoria': cat['Fondos'],   'nombre': 'Lomo Saltado',  'precio_actual': 35.00, 'tiempo_preparacion_min': 20},
    {'categoria': cat['Fondos'],   'nombre': 'Aji de Gallina','precio_actual': 28.00, 'tiempo_preparacion_min': 18},
    {'categoria': cat['Bebidas'],  'nombre': 'Inca Kola',     'precio_actual': 6.00,  'tiempo_preparacion_min': 2},
    {'categoria': cat['Bebidas'],  'nombre': 'Pisco Sour',    'precio_actual': 18.00, 'tiempo_preparacion_min': 5},
]
for pd in platos_data:
    Plato.objects.get_or_create(
        nombre=pd['nombre'],
        categoria=pd['categoria'],
        defaults={**pd, 'disponible': True}
    )

# ── 6. Misceláneos (UM y Métodos Pago) ───────────────────────────────────
UM_data = [
    {'nombre': 'Kilogramos', 'abreviatura': 'KG'},
    {'nombre': 'Litros',     'abreviatura': 'LT'},
    {'nombre': 'Unidades',   'abreviatura': 'UND'},
    {'nombre': 'Botella 750ml', 'abreviatura': 'BOT'},
]
for ud in UM_data:
    UnidadMedida.objects.get_or_create(abreviatura=ud['abreviatura'], defaults=ud)

pagos_data = [
    {'codigo': 'EFECTIVO', 'nombre': 'Efectivo',         'permite_vuelto': True},
    {'codigo': 'TARJETA',  'nombre': 'Tarjeta Débito/Crédito', 'permite_vuelto': False},
    {'codigo': 'YAPE',     'nombre': 'Yape / Plin',      'permite_vuelto': False},
]
for pd in pagos_data:
    MetodoPago.objects.get_or_create(codigo=pd['codigo'], defaults=pd)

# ── 7. Insumos e Inventario ──────────────────────────────────────────────
from apps.inventario.models import Insumo, RecetaInsumo

um = {u.abreviatura: u for u in UnidadMedida.objects.all()}

insumos_data = [
    {'nombre': 'Pescado (Reineta)', 'unidad_medida': um['KG'],  'stock_actual': 15.00, 'stock_minimo': 10.00, 'costo_unitario': 25.00},
    {'nombre': 'Limón Sutil',       'unidad_medida': um['KG'],  'stock_actual':  8.00, 'stock_minimo': 5.00,  'costo_unitario': 4.50},
    {'nombre': 'Cebolla Roja',      'unidad_medida': um['KG'],  'stock_actual': 12.00, 'stock_minimo': 8.00,  'costo_unitario': 3.20},
    {'nombre': 'Ají Amarillo',      'unidad_medida': um['KG'],  'stock_actual':  4.00, 'stock_minimo': 5.00,  'costo_unitario': 6.00},
    {'nombre': 'Lomo Fino',         'unidad_medida': um['KG'],  'stock_actual':  8.00, 'stock_minimo': 12.00, 'costo_unitario': 45.00},
    {'nombre': 'Pollo (Pechuga)',   'unidad_medida': um['KG'],  'stock_actual': 20.00, 'stock_minimo': 10.00, 'costo_unitario': 18.50},
    {'nombre': 'Papa Amarilla',     'unidad_medida': um['KG'],  'stock_actual': 18.00, 'stock_minimo': 15.00, 'costo_unitario': 4.00},
    {'nombre': 'Pisco Quebranta',   'unidad_medida': um['BOT'], 'stock_actual':  8.00, 'stock_minimo': 6.00,  'costo_unitario': 35.00},
    {'nombre': 'Inka Kola (600ml)', 'unidad_medida': um['UND'], 'stock_actual': 36.00, 'stock_minimo': 24.00, 'costo_unitario': 3.50},
    {'nombre': 'Masa Wantán',       'unidad_medida': um['KG'],  'stock_actual':  5.00, 'stock_minimo': 3.00,  'costo_unitario': 12.00},
]
for idat in insumos_data:
    sr = idat['stock_actual']
    # get_or_create: solo crea si no existe, NO sobreescribe stock en reinicios
    Insumo.objects.get_or_create(
        nombre=idat['nombre'],
        defaults={**idat, 'stock_real': sr, 'activo': True},
    )

ins = {i.nombre: i for i in Insumo.objects.all()}

# ── 8. Recetas (alineadas a la carta e insumos actuales) ────────────────
platos = {p.nombre: p for p in Plato.objects.all()}

RecetaInsumo.objects.all().delete()

recetas_data = [
    {'plato': platos['Ceviche'],       'insumo': ins['Pescado (Reineta)'], 'cantidad_por_porcion': 0.250},
    {'plato': platos['Ceviche'],       'insumo': ins['Limón Sutil'],       'cantidad_por_porcion': 0.080},
    {'plato': platos['Ceviche'],       'insumo': ins['Cebolla Roja'],      'cantidad_por_porcion': 0.050},
    {'plato': platos['Ceviche'],       'insumo': ins['Ají Amarillo'],      'cantidad_por_porcion': 0.030},
    {'plato': platos['Tequeños'],      'insumo': ins['Masa Wantán'],       'cantidad_por_porcion': 0.150},
    {'plato': platos['Lomo Saltado'],  'insumo': ins['Lomo Fino'],         'cantidad_por_porcion': 0.200},
    {'plato': platos['Lomo Saltado'],  'insumo': ins['Papa Amarilla'],     'cantidad_por_porcion': 0.300},
    {'plato': platos['Lomo Saltado'],  'insumo': ins['Cebolla Roja'],      'cantidad_por_porcion': 0.050},
    {'plato': platos['Lomo Saltado'],  'insumo': ins['Ají Amarillo'],      'cantidad_por_porcion': 0.020},
    {'plato': platos['Aji de Gallina'],'insumo': ins['Pollo (Pechuga)'],   'cantidad_por_porcion': 0.250},
    {'plato': platos['Aji de Gallina'],'insumo': ins['Ají Amarillo'],      'cantidad_por_porcion': 0.100},
    {'plato': platos['Aji de Gallina'],'insumo': ins['Cebolla Roja'],      'cantidad_por_porcion': 0.040},
    {'plato': platos['Inca Kola'],     'insumo': ins['Inka Kola (600ml)'],'cantidad_por_porcion': 1.000},
    {'plato': platos['Pisco Sour'],    'insumo': ins['Pisco Quebranta'],  'cantidad_por_porcion': 0.080},
    {'plato': platos['Pisco Sour'],    'insumo': ins['Limón Sutil'],       'cantidad_por_porcion': 0.040},
]
for rdat in recetas_data:
    RecetaInsumo.objects.create(**rdat)

print(f"✅ {Insumo.objects.count()} insumos y {RecetaInsumo.objects.count()} vínculos de receta")
print(f"✅ {Zona.objects.count()} zonas y {Mesa.objects.count()} mesas")
print(f"✅ {Plato.objects.count()} platos sembrados")
print("🎉 ¡Datos listos para PostgreSQL! Contraseña de prueba: pass123")
