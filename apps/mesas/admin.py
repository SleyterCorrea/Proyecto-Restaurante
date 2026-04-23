from django.contrib import admin
from .models import Mesa


@admin.register(Mesa)
class MesaAdmin(admin.ModelAdmin):
    list_display  = ['numero', 'piso', 'capacidad', 'estado']
    list_filter   = ['piso', 'estado']
    list_editable = ['estado']
    ordering      = ['piso', 'numero']
