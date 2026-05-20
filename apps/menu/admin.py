from django.contrib import admin
from .models import Categoria, Plato

@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'icono', 'orden', 'activo']
    list_filter = ['activo']
    ordering = ['orden']

@admin.register(Plato)
class PlatoAdmin(admin.ModelAdmin):
    list_display  = ['nombre', 'categoria', 'precio_actual', 'disponible', 'tiempo_preparacion_min', 'activo']
    list_filter   = ['categoria', 'disponible', 'activo']
    list_editable = ['precio_actual', 'disponible']
    search_fields = ['nombre', 'descripcion']
