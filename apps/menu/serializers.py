from rest_framework import serializers
from .models import Categoria, Plato
from apps.inventario.models import RecetaInsumo, Insumo

class RecetaInsumoSerializer(serializers.ModelSerializer):
    """Serializer para ingredientes de recetas en contexto de edición de platos."""
    insumo_id   = serializers.IntegerField()                     # readable + writable
    insumo_nombre = serializers.CharField(source='insumo.nombre', read_only=True)
    insumo_unidad = serializers.CharField(source='unidad_medida.simbolo', read_only=True)
    unidad_control = serializers.CharField(source='insumo.unidad_medida.simbolo', read_only=True)
    unidad_control_factor = serializers.DecimalField(
        source='insumo.unidad_medida.factor_conversion', max_digits=18,
        decimal_places=8, read_only=True
    )
    unidad_medida_id = serializers.IntegerField()
    magnitud_codigo = serializers.CharField(source='insumo.magnitud.codigo', read_only=True)
    unidades_compatibles = serializers.SerializerMethodField()
    cantidad_normalizada = serializers.SerializerMethodField()
    insumo_stock  = serializers.DecimalField(source='insumo.stock_real', max_digits=12, decimal_places=3, read_only=True)
    insumo_es_discreto = serializers.ReadOnlyField(source='unidad_medida.es_discreta')

    class Meta:
        model = RecetaInsumo
        fields = ['id', 'insumo_id', 'insumo_nombre', 'insumo_unidad',
                  'unidad_control', 'unidad_control_factor', 'unidad_medida_id', 'magnitud_codigo',
                  'unidades_compatibles', 'cantidad_normalizada', 'insumo_stock',
                  'insumo_es_discreto', 'cantidad_por_porcion',
                  'merma_porcentaje', 'activo']

    def get_unidades_compatibles(self, obj):
        return [
            {
                'id': unidad.id,
                'nombre': unidad.nombre,
                'simbolo': unidad.simbolo,
                'factor_conversion': str(unidad.factor_conversion),
                'es_discreta': unidad.es_discreta,
            }
            for unidad in obj.insumo.magnitud.unidades.filter(activo=True)
        ]

    def get_cantidad_normalizada(self, obj):
        return str(obj.cantidad_en_unidad_control)

    def create(self, validated_data):
        return RecetaInsumo.objects.create(**validated_data)

    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance

class CategoriaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Categoria
        fields = '__all__'

class PlatoSerializer(serializers.ModelSerializer):
    """Serializer para platos con información de disponibilidad e insumos."""
    categoria_nombre = serializers.ReadOnlyField(source='categoria.nombre')
    imagen_url = serializers.ReadOnlyField()
    receta = serializers.SerializerMethodField()
    receta_ids = serializers.PrimaryKeyRelatedField(
        write_only=True,
        many=True,
        queryset=RecetaInsumo.objects.all(),
        source='receta',
        required=False
    )

    class Meta:
        model = Plato
        fields = [
            'id', 'nombre', 'descripcion', 'categoria', 'categoria_nombre',
            'precio_actual', 'tiempo_preparacion_min', 'imagen', 'imagen_url',
            'disponible', 'activo', 'receta', 'receta_ids',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at', 'imagen_url']

    def get_receta(self, obj):
        recetas_activas = obj.receta.filter(activo=True).select_related(
            'insumo__unidad_medida', 'insumo__magnitud', 'unidad_medida'
        ).prefetch_related(
            'insumo__magnitud__unidades'
        )
        return RecetaInsumoSerializer(recetas_activas, many=True).data

    def validate_precio_actual(self, value):
        if value <= 0:
            raise serializers.ValidationError('El precio debe ser mayor a cero.')
        return value
