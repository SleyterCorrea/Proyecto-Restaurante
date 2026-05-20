from decimal import Decimal
from rest_framework import serializers
from .models import UnidadMedida, Insumo, RecetaInsumo, MovimientoInventario, OrdenCompra, OrdenCompraItem
from apps.menu.models import Plato

class UnidadMedidaSerializer(serializers.ModelSerializer):
    class Meta:
        model = UnidadMedida
        fields = '__all__'

class InsumoSerializer(serializers.ModelSerializer):
    unidad_nombre = serializers.ReadOnlyField(source='unidad_medida.nombre')
    unidad_abreviatura = serializers.ReadOnlyField(source='unidad_medida.abreviatura')

    class Meta:
        model = Insumo
        fields = [
            'id', 'nombre', 'categoria', 'unidad_medida', 'unidad_nombre', 'unidad_abreviatura',
            'stock_actual', 'stock_real', 'stock_minimo', 'costo_unitario', 'activo'
        ]

class RecetaInsumoSerializer(serializers.ModelSerializer):
    insumo_nombre = serializers.ReadOnlyField(source='insumo.nombre')
    unidad_abreviatura = serializers.ReadOnlyField(source='insumo.unidad_medida.abreviatura')

    class Meta:
        model = RecetaInsumo
        fields = '__all__'

class RecetaPorPlatoSerializer(serializers.ModelSerializer):
    receta = RecetaInsumoSerializer(many=True, read_only=True)

    class Meta:
        model = Plato
        fields = ['id', 'nombre', 'receta']

class MovimientoInventarioSerializer(serializers.ModelSerializer):
    usuario_nombre = serializers.ReadOnlyField(source='usuario.username')

    class Meta:
        model = MovimientoInventario
        fields = '__all__'

class AjusteStockSerializer(serializers.Serializer):
    cantidad = serializers.DecimalField(max_digits=12, decimal_places=3)
    motivo = serializers.CharField(max_length=255)
    tipo = serializers.ChoiceField(choices=['AJUSTE_POSITIVO', 'AJUSTE_NEGATIVO'])


class MermaSerializer(serializers.Serializer):
    cantidad = serializers.DecimalField(max_digits=12, decimal_places=3, min_value=Decimal('0.001'))
    causa = serializers.ChoiceField(choices=MovimientoInventario.CausaMerma.choices)
    observacion = serializers.CharField(max_length=500, required=False, allow_blank=True)


class OrdenCompraItemSerializer(serializers.ModelSerializer):
    insumo_nombre = serializers.ReadOnlyField(source='insumo.nombre')
    unidad_abreviatura = serializers.ReadOnlyField(source='insumo.unidad_medida.abreviatura')

    class Meta:
        model = OrdenCompraItem
        fields = ['id', 'insumo', 'insumo_nombre', 'unidad_abreviatura',
                  'cantidad_solicitada', 'cantidad_recibida', 'costo_unitario', 'subtotal']


class OrdenCompraSerializer(serializers.ModelSerializer):
    items = OrdenCompraItemSerializer(many=True, read_only=True)
    creado_por_nombre = serializers.ReadOnlyField(source='creado_por.username')
    estado_label = serializers.ReadOnlyField(source='get_estado_display')

    class Meta:
        model = OrdenCompra
        fields = ['id', 'codigo', 'proveedor', 'estado', 'estado_label',
                  'total_estimado', 'notas', 'creado_por', 'creado_por_nombre',
                  'recibido_por', 'fecha_envio', 'fecha_recepcion',
                  'created_at', 'updated_at', 'items']
        read_only_fields = ['codigo', 'total_estimado', 'creado_por', 'recibido_por',
                            'fecha_envio', 'fecha_recepcion']
