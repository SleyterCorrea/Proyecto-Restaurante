from django.db import models
from apps.menu.models import Plato
from django.conf import settings
from .managers import InsumoManager

class UnidadMedida(models.Model):
    nombre = models.CharField(max_length=60, unique=True)
    abreviatura = models.CharField(max_length=15, unique=True)
    tipo = models.CharField(max_length=20, blank=True, null=True)
    activo = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'unidad_medida'
        verbose_name = 'Unidad de Medida'

    def __str__(self):
        return f'{self.nombre} ({self.abreviatura})'

class Insumo(models.Model):
    class Categoria(models.TextChoices):
        PROTEINA   = 'PROTEINA',   'Proteínas'
        VEGETAL    = 'VEGETAL',    'Vegetales'
        BEBIDA     = 'BEBIDA',     'Bebidas'
        SECO       = 'SECO',       'Secos / Abarrotes'
        LACTEO     = 'LACTEO',     'Lácteos'
        CONDIMENTO = 'CONDIMENTO', 'Condimentos'
        OTRO       = 'OTRO',       'Otros'

    unidad_medida = models.ForeignKey(UnidadMedida, on_delete=models.PROTECT, related_name='insumos')
    nombre = models.CharField(max_length=120, unique=True)
    categoria = models.CharField(max_length=20, choices=Categoria.choices, default=Categoria.OTRO, db_index=True)
    # Stock contable / último inventario (referencia administrativa)
    stock_actual = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    # Stock operativo: se descuenta al marcar platos LISTO en cocina
    stock_real = models.DecimalField(max_digits=12, decimal_places=3, default=0, db_index=True)
    stock_minimo = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    costo_unitario = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    activo = models.BooleanField(default=True, db_index=True)
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
    cantidad_por_porcion = models.DecimalField(max_digits=12, decimal_places=4)
    merma_porcentaje = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    activo = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'receta_insumo'
        unique_together = ('plato', 'insumo')
        verbose_name = 'Ingrediente de Receta'

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
    cantidad = models.DecimalField(max_digits=12, decimal_places=3)
    stock_anterior = models.DecimalField(max_digits=12, decimal_places=3)
    stock_nuevo = models.DecimalField(max_digits=12, decimal_places=3)
    costo_unitario = models.DecimalField(max_digits=12, decimal_places=4, default=0)
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
    cantidad_solicitada = models.DecimalField(max_digits=12, decimal_places=3)
    cantidad_recibida = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    costo_unitario = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    subtotal = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    class Meta:
        db_table = 'orden_compra_item'
        unique_together = ('orden', 'insumo')
