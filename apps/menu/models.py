"""
Modelos para el catálogo del restaurante.
"""
from django.db import models


class Categoria(models.Model):
    """Categoría de platos (Entradas, Fondos, Postres, Bebidas, etc.)."""
    nombre = models.CharField(max_length=100)
    # Clase de ícono Bootstrap Icons o emoji para mostrar en el filtro
    icono  = models.CharField(max_length=50, default='bi-tag', help_text='Clase de Bootstrap Icons')
    orden  = models.PositiveSmallIntegerField(default=0, help_text='Orden de aparición en el menú')

    class Meta:
        ordering = ['orden', 'nombre']
        verbose_name = 'Categoría'
        verbose_name_plural = 'Categorías'

    def __str__(self):
        return self.nombre


class Plato(models.Model):
    """Plato del menú disponible para ordenar."""
    categoria    = models.ForeignKey(Categoria, on_delete=models.PROTECT, related_name='platos')
    nombre       = models.CharField(max_length=200)
    descripcion  = models.TextField(blank=True)
    precio       = models.DecimalField(max_digits=8, decimal_places=2)
    imagen       = models.ImageField(upload_to='platos/', blank=True, null=True)
    disponible   = models.BooleanField(default=True, help_text='Visible en el catálogo del mesero')
    tiempo_prep  = models.PositiveSmallIntegerField(default=15, help_text='Tiempo estimado de preparación en minutos')

    class Meta:
        ordering = ['categoria__orden', 'nombre']
        verbose_name = 'Plato'
        verbose_name_plural = 'Platos'

    def __str__(self):
        return f'{self.nombre} (${self.precio})'

    def imagen_url(self):
        """Devuelve la URL de la imagen o None si no tiene."""
        if self.imagen:
            return self.imagen.url
        return None
