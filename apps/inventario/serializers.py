from decimal import Decimal, ROUND_HALF_UP
from rest_framework import serializers
from apps.core.exceptions import AppError
from .models import (
    Insumo,
    InsumoCambioMedida,
    MagnitudMedida,
    MovimientoInventario,
    OrdenCompra,
    OrdenCompraItem,
    RecetaInsumo,
    UnidadMedida,
)
from .validators import validar_receta_sin_duplicados
from apps.menu.models import Plato

class MagnitudMedidaSerializer(serializers.ModelSerializer):
    class Meta:
        model = MagnitudMedida
        fields = ['id', 'codigo', 'nombre', 'activo']


class UnidadMedidaSerializer(serializers.ModelSerializer):
    es_discreta = serializers.ReadOnlyField()
    abreviatura = serializers.CharField(source='simbolo', read_only=True)
    magnitud_codigo = serializers.ReadOnlyField(source='magnitud.codigo')
    magnitud_nombre = serializers.ReadOnlyField(source='magnitud.nombre')

    class Meta:
        model = UnidadMedida
        fields = [
            'id', 'nombre', 'simbolo', 'abreviatura', 'magnitud',
            'magnitud_codigo', 'magnitud_nombre', 'factor_conversion',
            'es_base', 'es_discreta', 'activo',
        ]

class InsumoSerializer(serializers.ModelSerializer):
    unidad_nombre = serializers.ReadOnlyField(source='unidad_medida.nombre')
    unidad_abreviatura = serializers.ReadOnlyField(source='unidad_medida.simbolo')
    magnitud_codigo = serializers.ReadOnlyField(source='magnitud.codigo')
    magnitud_nombre = serializers.ReadOnlyField(source='magnitud.nombre')
    nivel_stock = serializers.ReadOnlyField()
    unidad_es_discreta = serializers.ReadOnlyField(source='unidad_medida.es_discreta')
    unidad_factor_conversion = serializers.ReadOnlyField(
        source='unidad_medida.factor_conversion'
    )
    unidades_compatibles = serializers.SerializerMethodField()
    medida_bloqueada = serializers.SerializerMethodField()

    class Meta:
        model = Insumo
        fields = [
            'id', 'nombre', 'categoria', 'magnitud', 'magnitud_codigo',
            'magnitud_nombre', 'unidad_medida', 'unidad_nombre', 'unidad_abreviatura',
            'unidad_es_discreta', 'unidad_factor_conversion',
            'unidades_compatibles', 'medida_bloqueada',
            'stock_actual', 'stock_real', 'stock_minimo', 'costo_unitario',
            'es_critico', 'medida_requiere_revision', 'agotado_desde',
            'stock_bajo_desde', 'activo', 'nivel_stock',
            'motivo_inactivacion', 'inactivado_en', 'inactivado_por',
        ]
        read_only_fields = [
            'activo', 'medida_requiere_revision', 'motivo_inactivacion',
            'inactivado_en', 'inactivado_por',
        ]

    def get_unidades_compatibles(self, obj):
        unidades = obj.magnitud.unidades.filter(activo=True).order_by('factor_conversion')
        return UnidadMedidaSerializer(unidades, many=True).data

    def get_medida_bloqueada(self, obj):
        return bool(
            obj.stock_actual != 0
            or obj.stock_real != 0
            or obj.movimientos.exists()
            or obj.platos.exists()
        )

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

    def validate(self, attrs):
        if self.instance:
            cambios_directos = {}
            for campo in ('stock_actual', 'stock_real'):
                if campo in attrs and attrs[campo] != getattr(self.instance, campo):
                    cambios_directos[campo] = (
                        'El stock no se edita desde la ficha del insumo. '
                        'Registra una entrada, merma o ajuste para conservar la trazabilidad.'
                    )
            if cambios_directos:
                raise serializers.ValidationError(cambios_directos)

        magnitud = attrs.get('magnitud') or (
            self.instance.magnitud if self.instance else None
        )
        unidad = attrs.get('unidad_medida') or (
            self.instance.unidad_medida if self.instance else None
        )
        if magnitud and unidad:
            from .services import InventarioService
            try:
                InventarioService.validar_compatibilidad_medida(magnitud, unidad)
            except AppError as exc:
                raise serializers.ValidationError({'unidad_medida': str(exc)})

        campos_stock = ('stock_actual', 'stock_real', 'stock_minimo')
        if unidad:
            if unidad.es_discreta:
                errores = {}
                for campo in campos_stock:
                    valor = attrs.get(campo)
                    valor_base = (
                        valor * unidad.factor_conversion
                        if valor is not None else None
                    )
                    if valor_base is not None and valor_base != valor_base.to_integral_value():
                        errores[campo] = (
                            'La cantidad debe equivaler a un número entero de unidades base.'
                        )
                if errores:
                    raise serializers.ValidationError(errores)
            else:
                precision = Decimal('0.000001')
                for campo in campos_stock:
                    valor = attrs.get(campo)
                    if valor is not None:
                        attrs[campo] = valor.quantize(
                            precision,
                            rounding=ROUND_HALF_UP,
                        )
        return attrs


class RecetaInsumoSerializer(serializers.ModelSerializer):
    insumo_nombre = serializers.ReadOnlyField(source='insumo.nombre')
    unidad_abreviatura = serializers.ReadOnlyField(source='unidad_medida.simbolo')
    unidad_control_abreviatura = serializers.ReadOnlyField(
        source='insumo.unidad_medida.simbolo'
    )
    magnitud_codigo = serializers.ReadOnlyField(source='insumo.magnitud.codigo')
    cantidad_normalizada = serializers.SerializerMethodField()

    class Meta:
        model = RecetaInsumo
        fields = '__all__'

    def get_cantidad_normalizada(self, obj):
        return str(obj.cantidad_en_unidad_control)

    def validate_cantidad_por_porcion(self, value):
        if value <= 0:
            raise serializers.ValidationError('La cantidad por porción debe ser mayor a 0.')
        return value

    def validate_merma_porcentaje(self, value):
        if not (0 <= value <= 100):
            raise serializers.ValidationError('El porcentaje de merma debe estar entre 0 y 100.')
        return value

    def validate(self, attrs):
        insumo = attrs.get('insumo') or (
            self.instance.insumo if self.instance else None
        )
        if insumo and not insumo.activo:
            raise serializers.ValidationError({'insumo': 'El insumo seleccionado está inactivo.'})

        unidad = attrs.get('unidad_medida') or (
            self.instance.unidad_medida if self.instance else None
        )
        if insumo and unidad is None:
            unidad = insumo.unidad_medida
            attrs['unidad_medida'] = unidad
        if insumo and unidad and unidad.magnitud_id != insumo.magnitud_id:
            raise serializers.ValidationError({
                'unidad_medida': (
                    'La unidad de la receta no es compatible con la magnitud del insumo.'
                )
            })
            
        plato = attrs.get('plato') or (self.instance.plato if self.instance else None)
        if plato and insumo:
            # Excluir la instancia actual si es una actualización
            exclude_pk = self.instance.pk if self.instance else None
            validar_receta_sin_duplicados(plato, insumo.id, exclude_pk)

        cantidad = attrs.get('cantidad_por_porcion')
        if cantidad is not None and unidad and unidad.es_discreta:
            cantidad_base = cantidad * unidad.factor_conversion
            if cantidad_base != cantidad_base.to_integral_value():
                raise serializers.ValidationError({
                    'cantidad_por_porcion': (
                        'La receta debe equivaler a un número entero de unidades base.'
                    )
                })
            
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
        max_digits=16, decimal_places=6, min_value=Decimal('0.000001'),
        error_messages={'min_value': 'La cantidad debe ser mayor a 0.'},
    )
    observacion = serializers.CharField(max_length=500, required=False, allow_blank=True)
    lote = serializers.CharField(max_length=80, required=False, allow_blank=True)
    costo_unitario = serializers.DecimalField(
        max_digits=12, decimal_places=4, min_value=Decimal('0'), required=False
    )


class AjusteStockSerializer(serializers.Serializer):
    cantidad = serializers.DecimalField(
        max_digits=16, decimal_places=6, min_value=Decimal('0.000001'),
        error_messages={'min_value': 'La cantidad debe ser mayor a 0.'},
    )
    motivo = serializers.CharField(max_length=255)
    tipo = serializers.ChoiceField(choices=['AJUSTE_POSITIVO', 'AJUSTE_NEGATIVO'])


class MermaSerializer(serializers.Serializer):
    cantidad = serializers.DecimalField(max_digits=16, decimal_places=6, min_value=Decimal('0.000001'))
    causa = serializers.ChoiceField(choices=MovimientoInventario.CausaMerma.choices)
    observacion = serializers.CharField(max_length=500, required=False, allow_blank=True)


class InactivarInsumoSerializer(serializers.Serializer):
    motivo = serializers.CharField(
        min_length=5,
        max_length=500,
        trim_whitespace=True,
        error_messages={
            'required': 'El motivo de inactivacion es obligatorio.',
            'min_length': 'El motivo debe tener al menos 5 caracteres.',
        },
    )


class CorregirMedidaInsumoSerializer(serializers.Serializer):
    magnitud = serializers.PrimaryKeyRelatedField(
        queryset=MagnitudMedida.objects.filter(activo=True)
    )
    unidad_medida = serializers.PrimaryKeyRelatedField(
        queryset=UnidadMedida.objects.filter(activo=True).select_related('magnitud')
    )
    factor_conversion = serializers.DecimalField(
        max_digits=18, decimal_places=8, min_value=Decimal('0.00000001')
    )
    motivo = serializers.CharField(min_length=5, max_length=500, trim_whitespace=True)

    def validate(self, attrs):
        if attrs['unidad_medida'].magnitud_id != attrs['magnitud'].id:
            raise serializers.ValidationError({
                'unidad_medida': 'La unidad no pertenece a la magnitud seleccionada.'
            })
        return attrs


class InsumoCambioMedidaSerializer(serializers.ModelSerializer):
    unidad_anterior_simbolo = serializers.ReadOnlyField(source='unidad_anterior.simbolo')
    unidad_nueva_simbolo = serializers.ReadOnlyField(source='unidad_nueva.simbolo')
    usuario_nombre = serializers.ReadOnlyField(source='usuario.username')

    class Meta:
        model = InsumoCambioMedida
        fields = '__all__'


class OrdenCompraItemSerializer(serializers.ModelSerializer):
    insumo_nombre = serializers.ReadOnlyField(source='insumo.nombre')
    unidad_abreviatura = serializers.ReadOnlyField(source='insumo.unidad_medida.simbolo')

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
