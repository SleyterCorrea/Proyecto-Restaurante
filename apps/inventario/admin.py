from django.contrib import admin
from .models import Insumo, UnidadMedida, RecetaInsumo, MovimientoInventario


@admin.register(Insumo)
class InsumoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'unidad_medida', 'stock_actual', 'stock_real', 'stock_minimo', 'costo_unitario', 'activo')
    list_filter  = ('activo', 'unidad_medida')
    search_fields = ('nombre',)
    ordering = ('nombre',)
    readonly_fields = ('created_at', 'updated_at')


@admin.register(UnidadMedida)
class UnidadMedidaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'abreviatura', 'tipo', 'activo')
    search_fields = ('nombre', 'abreviatura')


@admin.register(RecetaInsumo)
class RecetaInsumoAdmin(admin.ModelAdmin):
    list_display = ('plato', 'insumo', 'cantidad_por_porcion', 'merma_porcentaje', 'activo')
    list_filter  = ('activo',)
    search_fields = ('plato__nombre', 'insumo__nombre')


@admin.register(MovimientoInventario)
class MovimientoInventarioAdmin(admin.ModelAdmin):
    list_display = ('insumo', 'tipo_movimiento', 'cantidad', 'stock_anterior', 'stock_nuevo', 'usuario', 'created_at')
    list_filter  = ('tipo_movimiento',)
    search_fields = ('insumo__nombre',)
    ordering = ('-created_at',)
    readonly_fields = ('created_at', 'updated_at')
