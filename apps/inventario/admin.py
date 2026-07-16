from django.contrib import admin
from .forms import InsumoAdminForm, RecetaInsumoAdminForm
from .models import (
    Insumo,
    InsumoCambioMedida,
    MagnitudMedida,
    MovimientoInventario,
    RecetaInsumo,
    UnidadMedida,
)


@admin.register(Insumo)
class InsumoAdmin(admin.ModelAdmin):
    form = InsumoAdminForm
    list_display = ('nombre', 'magnitud', 'unidad_medida', 'stock_actual', 'stock_real', 'stock_minimo', 'costo_unitario', 'medida_requiere_revision', 'activo')
    list_filter  = ('activo', 'magnitud', 'unidad_medida', 'medida_requiere_revision')
    search_fields = ('nombre',)
    ordering = ('nombre',)
    readonly_fields = ('created_at', 'updated_at', 'inactivado_en', 'inactivado_por')

    def save_model(self, request, obj, form, change):
        if change:
            anterior = Insumo.objects.filter(pk=obj.pk).only('activo').first()
            if anterior and anterior.activo and not obj.activo:
                from django.utils import timezone
                obj.inactivado_en = timezone.now()
                obj.inactivado_por = request.user
        super().save_model(request, obj, form, change)

    def has_delete_permission(self, request, obj=None):
        return False

    def get_readonly_fields(self, request, obj=None):
        campos = list(super().get_readonly_fields(request, obj))
        if obj and (
            obj.stock_actual != 0
            or obj.stock_real != 0
            or obj.movimientos.exists()
            or obj.platos.exists()
        ):
            campos.extend(('magnitud', 'unidad_medida'))
        return tuple(campos)


@admin.register(MagnitudMedida)
class MagnitudMedidaAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'nombre', 'activo')
    list_filter = ('activo',)
    search_fields = ('codigo', 'nombre')


@admin.register(UnidadMedida)
class UnidadMedidaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'simbolo', 'magnitud', 'factor_conversion', 'es_base', 'activo')
    list_filter = ('magnitud', 'es_base', 'activo')
    search_fields = ('nombre', 'simbolo')


@admin.register(RecetaInsumo)
class RecetaInsumoAdmin(admin.ModelAdmin):
    form = RecetaInsumoAdminForm
    list_display = ('plato', 'insumo', 'cantidad_por_porcion', 'unidad_medida', 'merma_porcentaje', 'activo')
    list_filter  = ('activo',)
    search_fields = ('plato__nombre', 'insumo__nombre')


@admin.register(MovimientoInventario)
class MovimientoInventarioAdmin(admin.ModelAdmin):
    list_display = ('insumo', 'tipo_movimiento', 'cantidad', 'stock_anterior', 'stock_nuevo', 'usuario', 'created_at')
    list_filter  = ('tipo_movimiento',)
    search_fields = ('insumo__nombre',)
    ordering = ('-created_at',)
    readonly_fields = ('created_at', 'updated_at')


@admin.register(InsumoCambioMedida)
class InsumoCambioMedidaAdmin(admin.ModelAdmin):
    list_display = (
        'insumo', 'unidad_anterior', 'unidad_nueva', 'factor_conversion',
        'usuario', 'created_at',
    )
    readonly_fields = (
        'insumo', 'magnitud_anterior', 'magnitud_nueva', 'unidad_anterior',
        'unidad_nueva', 'factor_conversion', 'motivo', 'valores_anteriores',
        'valores_nuevos', 'usuario', 'created_at',
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
