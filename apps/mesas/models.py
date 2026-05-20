from django.db import models

class Zona(models.Model):
    """Modelo para las zonas del restaurante (Planta Baja, Terraza, etc.)."""
    nombre = models.CharField(max_length=60, unique=True)
    descripcion = models.CharField(max_length=150, blank=True, null=True)
    activo = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'zona'
        verbose_name = 'Zona'
        verbose_name_plural = 'Zonas'

    def __str__(self):
        return self.nombre

class Mesa(models.Model):
    """Mesa física del restaurante vinculada a una zona."""

    class Estado(models.TextChoices):
        LIBRE        = 'LIBRE',        'Libre'
        OCUPADA      = 'OCUPADA',      'Ocupada'
        RESERVADA    = 'RESERVADA',    'Reservada'
        LIMPIEZA     = 'LIMPIEZA',     'En Limpieza'
        POR_PAGAR    = 'POR_PAGAR',    'Por Pagar'

    zona       = models.ForeignKey(Zona, on_delete=models.PROTECT, related_name='mesas')
    numero     = models.PositiveSmallIntegerField(verbose_name='Número de mesa')
    capacidad  = models.PositiveSmallIntegerField(default=4, verbose_name='Capacidad (personas)')
    estado     = models.CharField(max_length=15, choices=Estado.choices, default=Estado.LIBRE)
    activo     = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'mesa'
        unique_together = ('zona', 'numero')
        ordering = ['zona', 'numero']
        verbose_name = 'Mesa'
        verbose_name_plural = 'Mesas'

    def __str__(self):
        return f'Mesa {self.numero} ({self.zona.nombre}) — {self.get_estado_display()}'

    @property
    def esta_libre(self):
        return self.estado == self.Estado.LIBRE

    @property
    def color_estado(self):
        mapa = {
            self.Estado.LIBRE:     'success',
            self.Estado.OCUPADA:   'danger',
            self.Estado.RESERVADA: 'warning',
            self.Estado.LIMPIEZA:  'secondary',
            self.Estado.POR_PAGAR: 'info',
        }
        return mapa.get(self.estado, 'light')

    # Mantener compatibilidad con el frontend antiguo (piso_label)
    @property
    def piso_label(self):
        return self.zona.nombre


class UnionMesas(models.Model):
    """
    Agrupa mesas físicas para ser tratadas como una unidad operativa.
    La unión es permanente (persiste entre comandas) y se disuelve solo manualmente.
    """
    mesa_principal = models.OneToOneField(
        Mesa,
        on_delete=models.CASCADE,
        related_name='union_como_principal',
        verbose_name='Mesa Principal'
    )
    mesas_secundarias = models.ManyToManyField(
        Mesa,
        related_name='uniones_como_secundaria',
        blank=True,
        verbose_name='Mesas Secundarias'
    )
    activa = models.BooleanField(default=True)
    capacidad_personalizada = models.IntegerField(
        null=True, 
        blank=True, 
        verbose_name='Capacidad Personalizada',
        help_text='Si se establece, anula la suma automática de las capacidades.'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'union_mesas'
        verbose_name = 'Unión de Mesas'
        verbose_name_plural = 'Uniones de Mesas'

    def __str__(self):
        secundarias = ', '.join([str(m.numero) for m in self.mesas_secundarias.all()])
        return f'Unión: Mesa {self.mesa_principal.numero} + [{secundarias}]'

    @property
    def capacidad_total(self):
        if self.capacidad_personalizada is not None:
            return self.capacidad_personalizada
        return self.mesa_principal.capacidad + sum(
            m.capacidad for m in self.mesas_secundarias.all()
        )

    @property
    def todas_las_mesas(self):
        return [self.mesa_principal] + list(self.mesas_secundarias.all())
