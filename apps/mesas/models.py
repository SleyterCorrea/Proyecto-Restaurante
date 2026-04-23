"""
Modelos para la gestión de mesas del restaurante.
"""
from django.db import models


class Mesa(models.Model):
    """Mesa física del restaurante."""

    class Piso(models.TextChoices):
        PLANTA_BAJA = 'PB', 'Planta Baja'
        PISO_1      = 'P1', 'Piso 1'
        PISO_2      = 'P2', 'Piso 2'
        TERRAZA     = 'TR', 'Terraza'

    class Estado(models.TextChoices):
        LIBRE        = 'LIBRE',        'Libre'
        OCUPADA      = 'OCUPADA',      'Ocupada'
        RESERVADA    = 'RESERVADA',    'Reservada'
        MANTENIMIENTO = 'MANTENIMIENTO', 'En Mantenimiento'

    numero     = models.PositiveSmallIntegerField(unique=True, verbose_name='Número de mesa')
    capacidad  = models.PositiveSmallIntegerField(default=4, verbose_name='Capacidad (personas)')
    piso       = models.CharField(max_length=2, choices=Piso.choices, default=Piso.PLANTA_BAJA)
    estado     = models.CharField(max_length=15, choices=Estado.choices, default=Estado.LIBRE)

    class Meta:
        ordering = ['piso', 'numero']
        verbose_name = 'Mesa'
        verbose_name_plural = 'Mesas'

    def __str__(self):
        return f'Mesa {self.numero} ({self.get_piso_display()}) — {self.get_estado_display()}'

    @property
    def esta_libre(self):
        return self.estado == self.Estado.LIBRE

    @property
    def color_estado(self):
        """Clase CSS de Bootstrap para el badge de estado."""
        mapa = {
            self.Estado.LIBRE:         'success',
            self.Estado.OCUPADA:       'danger',
            self.Estado.RESERVADA:     'warning',
            self.Estado.MANTENIMIENTO: 'secondary',
        }
        return mapa.get(self.estado, 'light')
