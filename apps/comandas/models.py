"""
Modelos para la gestión de comandas y líneas de pedido.
"""
from django.db import models
from django.contrib.auth import get_user_model
from apps.mesas.models import Mesa
from apps.menu.models import Plato

User = get_user_model()


class Comanda(models.Model):
    """Orden de servicio asociada a una mesa y un mesero."""

    class Estado(models.TextChoices):
        ABIERTA    = 'ABIERTA',    'Abierta'
        CERRADA    = 'CERRADA',    'Cerrada (Cobrada)'
        CANCELADA  = 'CANCELADA',  'Cancelada'

    mesa           = models.ForeignKey(Mesa, on_delete=models.PROTECT, related_name='comandas')
    mesero         = models.ForeignKey(User, on_delete=models.PROTECT, related_name='comandas',
                                       null=True, blank=True)
    estado         = models.CharField(max_length=10, choices=Estado.choices, default=Estado.ABIERTA)
    fecha_apertura = models.DateTimeField(auto_now_add=True)
    fecha_cierre   = models.DateTimeField(null=True, blank=True)
    notas          = models.TextField(blank=True, help_text='Notas generales de la mesa')

    class Meta:
        ordering = ['-fecha_apertura']
        verbose_name = 'Comanda'
        verbose_name_plural = 'Comandas'

    def __str__(self):
        return f'Comanda #{self.pk} — Mesa {self.mesa.numero} ({self.estado})'

    @property
    def total(self):
        """Suma del total de todas las líneas no canceladas."""
        return sum(
            linea.subtotal
            for linea in self.lineas.exclude(estado=LineaComanda.Estado.CANCELADO)
        )


class LineaComanda(models.Model):
    """Ítem individual dentro de una comanda (un plato con cantidad y estado de cocina)."""

    class Estado(models.TextChoices):
        PENDIENTE       = 'PENDIENTE',       'Pendiente'
        EN_PREPARACION  = 'EN_PREPARACION',  'En Preparación'
        LISTO           = 'LISTO',           'Listo para servir'
        CANCELADO       = 'CANCELADO',       'Cancelado'

    comanda         = models.ForeignKey(Comanda, on_delete=models.CASCADE, related_name='lineas')
    plato           = models.ForeignKey(Plato,   on_delete=models.PROTECT, related_name='lineas')
    cantidad        = models.PositiveSmallIntegerField(default=1)
    # Snapshot del precio al momento de ordenar (importante para historial)
    precio_unitario = models.DecimalField(max_digits=8, decimal_places=2)
    estado          = models.CharField(max_length=15, choices=Estado.choices, default=Estado.PENDIENTE)
    notas_cocina    = models.CharField(max_length=255, blank=True,
                                       help_text='Ej: Sin cebolla, término medio')

    class Meta:
        verbose_name = 'Línea de Comanda'
        verbose_name_plural = 'Líneas de Comanda'

    def __str__(self):
        return f'{self.cantidad}x {self.plato.nombre} [{self.get_estado_display()}]'

    @property
    def subtotal(self):
        return self.precio_unitario * self.cantidad
