from django.contrib import admin
from .models import Zona, Mesa

@admin.register(Zona)
class ZonaAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'descripcion', 'activo']
    list_filter = ['activo']

@admin.register(Mesa)
class MesaAdmin(admin.ModelAdmin):
    list_display  = ['numero', 'zona', 'capacidad', 'estado', 'activo']
    list_filter   = ['zona', 'estado', 'activo']
    list_editable = ['estado']
    ordering      = ['zona', 'numero']
