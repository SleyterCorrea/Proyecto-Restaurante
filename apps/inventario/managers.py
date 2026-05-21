"""Managers personalizados para el módulo de inventario."""
from django.db import models
from django.db.models import F


class InsumoManager(models.Manager):
    def activos(self):
        return self.filter(activo=True)

    def criticos(self):
        """Stock real <= stock mínimo (incluye agotados)."""
        return self.filter(activo=True, stock_real__lte=F('stock_minimo'))

    def agotados(self):
        return self.filter(activo=True, stock_real__lte=0)

    def bajo_stock(self):
        """Stock real > 0 pero <= stock mínimo."""
        return self.filter(activo=True, stock_real__gt=0, stock_real__lte=F('stock_minimo'))

    def con_stock_suficiente(self):
        return self.filter(activo=True, stock_real__gt=F('stock_minimo'))

    def para_recetas(self):
        """Insumos disponibles para asignar a recetas, con unidad precargada."""
        return self.activos().select_related('unidad_medida').order_by('nombre')
