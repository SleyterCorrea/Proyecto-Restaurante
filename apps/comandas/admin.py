from django.contrib import admin
from .models import Comanda, LineaComanda


class LineaComandaInline(admin.TabularInline):
    model  = LineaComanda
    extra  = 0
    fields = ['plato', 'cantidad', 'precio_unitario', 'estado', 'notas_cocina']
    readonly_fields = ['precio_unitario']


@admin.register(Comanda)
class ComandaAdmin(admin.ModelAdmin):
    list_display  = ['__str__', 'mesa', 'mesero', 'estado', 'fecha_apertura']
    list_filter   = ['estado', 'fecha_apertura']
    inlines       = [LineaComandaInline]
    readonly_fields = ['fecha_apertura']


@admin.register(LineaComanda)
class LineaComandaAdmin(admin.ModelAdmin):
    list_display = ['comanda', 'plato', 'cantidad', 'precio_unitario', 'estado']
    list_filter  = ['estado']
