from django.contrib import admin
from .models import Categoria, Plato


@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'icono', 'orden']
    ordering = ['orden']


@admin.register(Plato)
class PlatoAdmin(admin.ModelAdmin):
    list_display  = ['nombre', 'categoria', 'precio', 'disponible', 'tiempo_prep']
    list_filter   = ['categoria', 'disponible']
    list_editable = ['precio', 'disponible']
    search_fields = ['nombre', 'descripcion']
