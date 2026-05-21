"""Validaciones de negocio del módulo de inventario."""
from decimal import Decimal
from rest_framework.exceptions import ValidationError

from .models import Insumo, RecetaInsumo


def validar_cantidad_positiva(cantidad, campo='cantidad'):
    if cantidad is None or Decimal(str(cantidad)) <= 0:
        raise ValidationError({campo: 'El valor debe ser mayor a 0.'})


def validar_stock_no_negativo(insumo: Insumo, cantidad: Decimal, operacion: str = 'descuento'):
    """Lanza ValidationError si el descuento dejaría el stock en negativo."""
    if insumo.stock_real < cantidad:
        raise ValidationError(
            f'Stock insuficiente para "{insumo.nombre}": '
            f'disponible {insumo.stock_real}, requerido {cantidad} ({operacion}).'
        )


def validar_insumo_activo(insumo: Insumo):
    if not insumo.activo:
        raise ValidationError(f'El insumo "{insumo.nombre}" está inactivo.')


def validar_receta_sin_duplicados(plato, insumo_id, exclude_pk=None):
    """Verifica que el insumo no esté ya en la receta del plato."""
    qs = RecetaInsumo.objects.filter(plato=plato, insumo_id=insumo_id, activo=True)
    if exclude_pk:
        qs = qs.exclude(pk=exclude_pk)
    if qs.exists():
        raise ValidationError(f'El insumo ya está en la receta de este plato.')


def validar_precio_no_negativo(precio, campo='precio'):
    if Decimal(str(precio)) < 0:
        raise ValidationError({campo: 'El precio no puede ser negativo.'})
