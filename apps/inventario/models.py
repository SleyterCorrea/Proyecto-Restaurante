from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.functions import Lower
from apps.menu.models import Plato
from django.conf import settings
from .managers import InsumoManager

class MagnitudMedida(models.Model):
    codigo = models.SlugField(max_length=30, unique=True)
    nombre = models.CharField(max_length=60, unique=True)
    activo = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'magnitud_medida'
        verbose_name = 'Magnitud de medida'
        verbose_name_plural = 'Magnitudes de medida'
        ordering = ('nombre',)
        constraints = [
            models.UniqueConstraint(
                Lower('nombre'), name='magnitud_nombre_ci_uniq'
            ),
        ]

    def clean(self):
        self.codigo = (self.codigo or '').strip().upper()
        self.nombre = ' '.join((self.nombre or '').split())
        if not self.codigo:
            raise ValidationError({'codigo': 'El código de la magnitud es obligatorio.'})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.nombre


class UnidadMedida(models.Model):
    TIPO_DISCRETA = 'DISCRETA'
    TIPO_CONTINUA = 'CONTINUA'
    nombre = models.CharField(max_length=60, unique=True)
    simbolo = models.CharField(max_length=15, unique=True)
    magnitud = models.ForeignKey(
        MagnitudMedida,
        on_delete=models.PROTECT,
        related_name='unidades',
    )
    factor_conversion = models.DecimalField(
        max_digits=18,
        decimal_places=8,
        default=Decimal('1'),
        help_text='Cantidad de unidades base equivalentes a una unidad de medida.',
    )
    es_base = models.BooleanField(default=False)
    tipo = models.CharField(max_length=20, blank=True, null=True)
    activo = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'unidad_medida'
        verbose_name = 'Unidad de Medida'
        ordering = ('magnitud__nombre', 'factor_conversion', 'nombre')
        constraints = [
            models.UniqueConstraint(
                Lower('nombre'), name='unidad_nombre_ci_uniq'
            ),
            models.UniqueConstraint(
                Lower('simbolo'), name='unidad_simbolo_ci_uniq'
            ),
            models.UniqueConstraint(
                fields=('magnitud',),
                condition=models.Q(es_base=True),
                name='unidad_base_magnitud_uniq',
            ),
            models.CheckConstraint(
                check=models.Q(factor_conversion__gt=0),
                name='unidad_factor_positivo_ck',
            ),
        ]

    def __str__(self):
        return f'{self.nombre} ({self.simbolo})'

    @property
    def abreviatura(self):
        """Alias temporal para consumidores que aún esperan el contrato anterior."""
        return self.simbolo

    def clean(self):
        self.nombre = ' '.join((self.nombre or '').split())
        self.simbolo = (self.simbolo or '').strip().lower()
        if self.factor_conversion is None or self.factor_conversion <= 0:
            raise ValidationError({
                'factor_conversion': 'El factor de conversión debe ser mayor a cero.'
            })
        if self.es_base and self.factor_conversion != Decimal('1'):
            raise ValidationError({
                'factor_conversion': 'La unidad base debe tener factor de conversión 1.'
            })
        if self.magnitud_id and not self.magnitud.activo:
            raise ValidationError({'magnitud': 'La magnitud seleccionada está inactiva.'})

        if self.pk:
            anterior = type(self).objects.filter(pk=self.pk).values(
                'magnitud_id', 'factor_conversion', 'es_base'
            ).first()
            cambia_conversion = anterior and (
                anterior['magnitud_id'] != self.magnitud_id
                or anterior['factor_conversion'] != self.factor_conversion
                or anterior['es_base'] != self.es_base
            )
            if cambia_conversion and (
                self.insumos.exists() or self.recetas.exists()
            ):
                raise ValidationError({
                    'factor_conversion': (
                        'No se puede cambiar la magnitud, factor o referencia de una '
                        'unidad utilizada. Cree otra unidad o migre los datos de forma explicita.'
                    )
                })

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def convertir_a(self, cantidad, unidad_destino):
        """Convierte una cantidad a otra unidad de la misma magnitud usando Decimal."""
        if not unidad_destino or self.magnitud_id != unidad_destino.magnitud_id:
            raise ValidationError(
                'Solo se pueden convertir unidades pertenecientes a la misma magnitud.'
            )
        try:
            cantidad_decimal = Decimal(str(cantidad))
        except (InvalidOperation, TypeError, ValueError):
            raise ValidationError('La cantidad a convertir no es válida.')
        return (
            cantidad_decimal * self.factor_conversion
            / unidad_destino.factor_conversion
        )

    @property
    def es_discreta(self):
        """Las unidades contables no admiten fracciones en recetas o stock."""
        return (self.tipo or '').upper() == self.TIPO_DISCRETA

class Insumo(models.Model):
    class Categoria(models.TextChoices):
        PROTEINA   = 'PROTEINA',   'Proteínas'
        VEGETAL    = 'VEGETAL',    'Vegetales'
        BEBIDA     = 'BEBIDA',     'Bebidas'
        SECO       = 'SECO',       'Secos / Abarrotes'
        LACTEO     = 'LACTEO',     'Lácteos'
        CONDIMENTO = 'CONDIMENTO', 'Condimentos'
        OTRO       = 'OTRO',       'Otros'

    magnitud = models.ForeignKey(
        MagnitudMedida,
        on_delete=models.PROTECT,
        related_name='insumos',
    )
    unidad_medida = models.ForeignKey(UnidadMedida, on_delete=models.PROTECT, related_name='insumos')
    nombre = models.CharField(max_length=120, unique=True)
    categoria = models.CharField(max_length=20, choices=Categoria.choices, default=Categoria.OTRO, db_index=True)
    # Stock contable / último inventario (referencia administrativa)
    stock_actual = models.DecimalField(max_digits=16, decimal_places=6, default=0)
    # Stock operativo: se valida al pedir y se descuenta al confirmar el cobro.
    stock_real = models.DecimalField(max_digits=16, decimal_places=6, default=0, db_index=True)
    stock_minimo = models.DecimalField(max_digits=16, decimal_places=6, default=0)
    costo_unitario = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    es_critico = models.BooleanField(default=False, db_index=True)
    medida_requiere_revision = models.BooleanField(default=False, db_index=True)
    agotado_desde = models.DateTimeField(null=True, blank=True)
    stock_bajo_desde = models.DateTimeField(null=True, blank=True)
    activo = models.BooleanField(default=True, db_index=True)
    motivo_inactivacion = models.TextField(blank=True, default='')
    inactivado_en = models.DateTimeField(null=True, blank=True)
    inactivado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='insumos_inactivados',
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = InsumoManager()

    class Meta:
        db_table = 'insumo'
        verbose_name = 'Insumo'
        indexes = [
            models.Index(fields=['activo', 'stock_real'], name='insumo_activo_stock_idx'),
            models.Index(fields=['categoria', 'activo'], name='insumo_categoria_idx'),
        ]

    def __str__(self):
        return self.nombre

    def clean(self):
        errores = {}
        if not self.activo and len((self.motivo_inactivacion or '').strip()) < 5:
            errores['motivo_inactivacion'] = (
                'Todo insumo inactivo debe conservar un motivo de al menos 5 caracteres.'
            )
        if self.magnitud_id and self.unidad_medida_id:
            if self.unidad_medida.magnitud_id != self.magnitud_id:
                errores['unidad_medida'] = (
                    'La unidad de control no pertenece a la magnitud seleccionada.'
                )
            elif not self.unidad_medida.activo:
                errores['unidad_medida'] = 'La unidad de control seleccionada está inactiva.'
        if self.magnitud_id and not self.magnitud.activo:
            errores['magnitud'] = 'La magnitud seleccionada está inactiva.'

        if self.unidad_medida_id and self.unidad_medida.es_discreta:
            for campo in ('stock_actual', 'stock_real', 'stock_minimo'):
                valor = getattr(self, campo, None)
                if valor is None:
                    continue
                valor_base = valor * self.unidad_medida.factor_conversion
                if valor_base != valor_base.to_integral_value():
                    errores[campo] = (
                        'La cantidad debe equivaler a unidades base enteras.'
                    )

        if self.pk:
            anterior = type(self).objects.filter(pk=self.pk).values(
                'magnitud_id', 'unidad_medida_id', 'stock_actual', 'stock_real'
            ).first()
            medida_cambio = anterior and (
                anterior['magnitud_id'] != self.magnitud_id
                or anterior['unidad_medida_id'] != self.unidad_medida_id
            )
            if medida_cambio:
                tiene_cantidades = (
                    anterior['stock_actual'] != 0 or anterior['stock_real'] != 0
                )
                tiene_historial = self.movimientos.exists() or self.platos.exists()
                if tiene_cantidades or tiene_historial:
                    errores['unidad_medida'] = (
                        'No se puede cambiar la magnitud o unidad de un insumo con stock, '
                        'recetas o movimientos. Registra una presentación nueva o realiza '
                        'un proceso explícito de migración.'
                    )
        if errores:
            raise ValidationError(errores)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError(
            'Los insumos no se eliminan fisicamente; deben inactivarse con motivo.'
        )

    def puede_descontar(self, cantidad):
        """Verifica si hay stock suficiente para descontar."""
        return self.stock_real >= cantidad

    @property
    def nivel_stock(self):
        """Retorna el nivel de stock: 'agotado', 'bajo', 'optimo'."""
        if self.stock_real <= 0:
            return 'agotado'
        if self.stock_real <= self.stock_minimo:
            return 'bajo'
        return 'optimo'

    @property
    def necesita_reposicion(self):
        """Retorna True si el insumo necesita reposición."""
        return self.activo and self.stock_real <= self.stock_minimo

class RecetaInsumo(models.Model):
    plato = models.ForeignKey(Plato, on_delete=models.CASCADE, related_name='receta')
    insumo = models.ForeignKey(Insumo, on_delete=models.PROTECT, related_name='platos')
    unidad_medida = models.ForeignKey(
        UnidadMedida,
        on_delete=models.PROTECT,
        related_name='recetas',
    )
    cantidad_por_porcion = models.DecimalField(max_digits=16, decimal_places=6)
    merma_porcentaje = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    activo = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'receta_insumo'
        unique_together = ('plato', 'insumo')
        verbose_name = 'Ingrediente de Receta'

    def clean(self):
        errores = {}
        if self.insumo_id and self.unidad_medida_id:
            if self.unidad_medida.magnitud_id != self.insumo.magnitud_id:
                errores['unidad_medida'] = (
                    'La unidad de la receta no es compatible con la magnitud del insumo.'
                )
        if self.cantidad_por_porcion is not None and self.cantidad_por_porcion <= 0:
            errores['cantidad_por_porcion'] = 'La cantidad por porción debe ser mayor a cero.'
        if (
            self.unidad_medida_id
            and self.cantidad_por_porcion is not None
            and self.unidad_medida.es_discreta
        ):
            cantidad_base = (
                self.cantidad_por_porcion * self.unidad_medida.factor_conversion
            )
            if cantidad_base != cantidad_base.to_integral_value():
                errores['cantidad_por_porcion'] = (
                    'La cantidad debe equivaler a unidades base enteras.'
                )
        if errores:
            raise ValidationError(errores)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    @property
    def cantidad_en_unidad_control(self):
        return self.unidad_medida.convertir_a(
            self.cantidad_por_porcion,
            self.insumo.unidad_medida,
        )

    @property
    def cantidad_en_unidad_base(self):
        return self.cantidad_por_porcion * self.unidad_medida.factor_conversion


class InsumoCambioMedida(models.Model):
    insumo = models.ForeignKey(
        Insumo, on_delete=models.PROTECT, related_name='cambios_medida'
    )
    magnitud_anterior = models.ForeignKey(
        MagnitudMedida, on_delete=models.PROTECT, related_name='+'
    )
    magnitud_nueva = models.ForeignKey(
        MagnitudMedida, on_delete=models.PROTECT, related_name='+'
    )
    unidad_anterior = models.ForeignKey(
        UnidadMedida, on_delete=models.PROTECT, related_name='+'
    )
    unidad_nueva = models.ForeignKey(
        UnidadMedida, on_delete=models.PROTECT, related_name='+'
    )
    factor_conversion = models.DecimalField(max_digits=18, decimal_places=8)
    motivo = models.TextField()
    valores_anteriores = models.JSONField(default=dict)
    valores_nuevos = models.JSONField(default=dict)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name='correcciones_medida_inventario'
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = 'insumo_cambio_medida'
        verbose_name = 'Correccion de medida de insumo'
        ordering = ('-created_at',)

    def __str__(self):
        return f'{self.insumo}: {self.unidad_anterior} -> {self.unidad_nueva}'

class MovimientoInventario(models.Model):
    class TipoMovimiento(models.TextChoices):
        ENTRADA    = 'ENTRADA',         'Entrada'
        SALIDA     = 'SALIDA',          'Salida'
        CONSUMO    = 'CONSUMO',         'Consumo (Cocina)'
        AJUSTE_POS = 'AJUSTE_POSITIVO', 'Ajuste Positivo'
        AJUSTE_NEG = 'AJUSTE_NEGATIVO', 'Ajuste Negativo'
        MERMA      = 'MERMA',           'Merma / Pérdida'

    class CausaMerma(models.TextChoices):
        VENCIDO  = 'VENCIDO',  'Vencido'
        DAÑADO   = 'DAÑADO',   'Dañado'
        DERRAME  = 'DERRAME',  'Derrame'
        ROBO     = 'ROBO',     'Robo / Faltante'
        ERROR    = 'ERROR',    'Error de preparación'
        OTRO     = 'OTRO',     'Otro'

    insumo = models.ForeignKey(Insumo, on_delete=models.PROTECT, related_name='movimientos')
    tipo_movimiento = models.CharField(max_length=20, choices=TipoMovimiento.choices)
    cantidad = models.DecimalField(max_digits=16, decimal_places=6)
    stock_anterior = models.DecimalField(max_digits=16, decimal_places=6)
    stock_nuevo = models.DecimalField(max_digits=16, decimal_places=6)
    costo_unitario = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    lote = models.CharField(max_length=80, blank=True, null=True, db_index=True)
    referencia_tipo = models.CharField(max_length=30, blank=True, null=True)
    referencia_id = models.BigIntegerField(blank=True, null=True)
    causa_merma = models.CharField(max_length=20, choices=CausaMerma.choices, blank=True, null=True,
                                    help_text='Solo aplica cuando tipo_movimiento=MERMA')
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    observacion = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'movimiento_inventario'
        verbose_name = 'Movimiento de Inventario'
        indexes = [
            models.Index(fields=['insumo', '-created_at'], name='mov_insumo_fecha_idx'),
            models.Index(fields=['tipo_movimiento', '-created_at'], name='mov_tipo_fecha_idx'),
        ]


# ─── Órdenes de Compra ──────────────────────────────────────────────────────
class OrdenCompra(models.Model):
    """Orden de compra a proveedor. Cuando se marca RECIBIDA, suma al stock automáticamente."""

    class Estado(models.TextChoices):
        BORRADOR  = 'BORRADOR',  'Borrador'
        ENVIADA   = 'ENVIADA',   'Enviada al proveedor'
        RECIBIDA  = 'RECIBIDA',  'Recibida'
        CANCELADA = 'CANCELADA', 'Cancelada'

    codigo = models.CharField(max_length=30, unique=True, blank=True)
    proveedor = models.CharField(max_length=120, blank=True)
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.BORRADOR, db_index=True)
    total_estimado = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    notas = models.TextField(blank=True, null=True)
    creado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                    related_name='ordenes_creadas')
    recibido_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                      related_name='ordenes_recibidas', blank=True, null=True)
    fecha_envio = models.DateTimeField(blank=True, null=True)
    fecha_recepcion = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'orden_compra'
        verbose_name = 'Orden de Compra'
        ordering = ['-created_at']

    def __str__(self):
        return self.codigo or f'OC-{self.pk}'


class OrdenCompraItem(models.Model):
    orden = models.ForeignKey(OrdenCompra, on_delete=models.CASCADE, related_name='items')
    insumo = models.ForeignKey(Insumo, on_delete=models.PROTECT, related_name='ordenes_items')
    cantidad_solicitada = models.DecimalField(max_digits=16, decimal_places=6)
    cantidad_recibida = models.DecimalField(max_digits=16, decimal_places=6, default=0)
    costo_unitario = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    subtotal = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    class Meta:
        db_table = 'orden_compra_item'
        unique_together = ('orden', 'insumo')
