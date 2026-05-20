from django.db import models

class Categoria(models.Model):
    """Categoría de platos (Entradas, Fondos, etc.) según el esquema SQL."""
    nombre = models.CharField(max_length=80, unique=True)
    activo = models.BooleanField(default=True)
    
    # Campo extra para mantener compatibilidad con iconos del frontend actual
    icono = models.CharField(max_length=50, default='bi-tag', help_text='Clase de Bootstrap Icons')
    orden = models.PositiveSmallIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'categoria_plato'
        ordering = ['orden', 'nombre']
        verbose_name = 'Categoría'
        verbose_name_plural = 'Categorías'

    def __str__(self):
        return self.nombre

class Plato(models.Model):
    """Plato del menú según el esquema SQL."""
    categoria = models.ForeignKey(Categoria, on_delete=models.PROTECT, related_name='platos')
    nombre = models.CharField(max_length=120)
    descripcion = models.TextField(blank=True, null=True)
    precio_actual = models.DecimalField(max_digits=10, decimal_places=2)
    tiempo_preparacion_min = models.PositiveSmallIntegerField(default=0)
    disponible = models.BooleanField(default=True)
    imagen = models.ImageField(upload_to='platos/', blank=True, null=True)
    activo = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'plato'
        unique_together = ('categoria', 'nombre')
        ordering = ['categoria__orden', 'nombre']
        verbose_name = 'Plato'
        verbose_name_plural = 'Platos'

    def __str__(self):
        return f'{self.nombre} (${self.precio_actual})'

    def imagen_url(self):
        if self.imagen:
            return self.imagen.url
        return None

    # Alias para compatibilidad con código existente
    @property
    def precio(self):
        return self.precio_actual

    @property
    def tiempo_prep(self):
        return self.tiempo_preparacion_min
