from decimal import Decimal
from rest_framework import serializers
from .models import UnidadMedida, Insumo, RecetaInsumo, MovimientoInventario, OrdenCompra, OrdenCompraItem
from .validators import validar_receta_sin_duplicados
from apps.menu.models import Plato

class UnidadMedidaSerializer(serializers.ModelSerializer):
    class Meta:
        model = UnidadMedida
        fields = '__all__'

class InsumoSerializer(serializers.ModelSerializer):
    unidad_nombre = serializers.ReadOnlyField(source='unidad_medida.nombre')
    unidad_abreviatura = serializers.ReadOnlyField(source='unidad_medida.abreviatura')
    nivel_stock = serializers.ReadOnlyField()

    class Meta:
        model = Insumo
        fields = [
            'id', 'nombre', 'categoria', 'unidad_medida', 'unidad_nombre', 'unidad_abreviatura',
            'stock_actual', 'stock_real', 'stock_minimo', 'costo_unitario', 'activo', 'nivel_stock',
        ]

    def validate_stock_minimo(self, value):
        if value < 0:
            raise serializers.ValidationError('El stock mínimo no puede ser negativo.')
        return value

    def validate_costo_unitario(self, value):
        if value < 0:
            raise serializers.ValidationError('El costo unitario no puede ser negativo.')
        return value

    def validate_stock_actual(self, value):
        if value < 0:
            raise serializers.ValidationError('El stock no puede ser negativo.')
        return value

    def validate_stock_real(self, value):
        if value < 0:
            raise serializers.ValidationError('El stock real no puede ser negativo.')
        return value


class RecetaInsumoSerializer(serializers.ModelSerializer):
    insumo_nombre = serializers.ReadOnlyField(source='insumo.nombre')
    unidad_abreviatura = serializers.ReadOnlyField(source='insumo.unidad_medida.abreviatura')

    class Meta:
        model = RecetaInsumo
        fields = '__all__'

    def validate_cantidad_por_porcion(self, value):
        if value <= 0:
            raise serializers.ValidationError('La cantidad por porción debe ser mayor a 0.')
        return value

    def validate_merma_porcentaje(self, value):
        if not (0 <= value <= 100):
            raise serializers.ValidationError('El porcentaje de merma debe estar entre 0 y 100.')
        return value

    def validate(self, attrs):
        insumo = attrs.get('insumo')
        if insumo and not insumo.activo:
            raise serializers.ValidationError({'insumo': 'El insumo seleccionado está inactivo.'})
            
        plato = attrs.get('plato') or (self.instance.plato if self.instance else None)
        if plato and insumo:
            # Excluir la instancia actual si es una actualización
            exclude_pk = self.instance.pk if self.instance else None
            validar_receta_sin_duplicados(plato, insumo.id, exclude_pk)
            
        return attrs


class RecetaPorPlatoSerializer(serializers.ModelSerializer):
    receta = RecetaInsumoSerializer(many=True, read_only=True)

    class Meta:
        model = Plato
        fields = ['id', 'nombre', 'receta']

class MovimientoInventarioSerializer(serializers.ModelSerializer):
    usuario_nombre = serializers.ReadOnlyField(source='usuario.username')
    insumo_nombre = serializers.ReadOnlyField(source='insumo.nombre')
    tipo_label = serializers.ReadOnlyField(source='get_tipo_movimiento_display')

    class Meta:
        model = MovimientoInventario
        fields = '__all__'


class ReponerSerializer(serializers.Serializer):
    cantidad = serializers.DecimalField(
        max_digits=12, decimal_places=3, min_value=Decimal('0.001'),
        error_messages={'min_value': 'La cantidad debe ser mayor a 0.'},
    )
    observacion = serializers.CharField(max_length=500, required=False, allow_blank=True)


class AjusteStockSerializer(serializers.Serializer):
    cantidad = serializers.DecimalField(
        max_digits=12, decimal_places=3, min_value=Decimal('0.001'),
        error_messages={'min_value': 'La cantidad debe ser mayor a 0.'},
    )
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
