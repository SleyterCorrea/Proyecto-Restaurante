from django.db import models
from django.conf import settings
from apps.comandas.models import Comanda

class CajaTurno(models.Model):
    class Estado(models.TextChoices):
        ABIERTA = 'ABIERTA', 'Abierta'
        CERRADA = 'CERRADA', 'Cerrada'
        ANULADA = 'ANULADA', 'Anulada'

    PUNTO_CAJA_CHOICES = [
        ('PLANTA_BAJA', 'Planta Baja'),
        ('PISO_1', 'Piso 1'),
        ('TERRAZA', 'Terraza'),
    ]

    codigo_turno = models.CharField(max_length=30, unique=True)
    cajero = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='turnos_caja')
    saldo_inicial = models.DecimalField(max_digits=12, decimal_places=2)
    saldo_final = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    total_ventas = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_efectivo = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_tarjeta = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.ABIERTA)
    punto_caja = models.CharField(max_length=20, choices=PUNTO_CAJA_CHOICES, default='PLANTA_BAJA')
    arqueo_fisico = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True,
                                        help_text="Monto contado físicamente al cerrar")
    diferencia = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True,
                                     help_text="Diferencia entre sistema y físico")
    fecha_apertura = models.DateTimeField(auto_now_add=True)
    fecha_cierre = models.DateTimeField(null=True, blank=True)
    observacion = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'caja_turno'
        verbose_name = 'Turno de Caja'

    def __str__(self):
        return f'Turno {self.codigo_turno} — {self.cajero.username}'

class MetodoPago(models.Model):
    codigo = models.CharField(max_length=20, unique=True)
    nombre = models.CharField(max_length=60, unique=True)
    requiere_referencia = models.BooleanField(default=False)
    permite_vuelto = models.BooleanField(default=True)
    activo = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'metodo_pago'
        verbose_name = 'Método de Pago'

    def __str__(self):
        return self.nombre

class Pago(models.Model):
    class Estado(models.TextChoices):
        PENDIENTE = 'PENDIENTE', 'Pendiente'
        PAGADO    = 'PAGADO',    'Pagado'
        ANULADO   = 'ANULADO',   'Anulado'
        PERDIDA   = 'PERDIDA',   'Pérdida (No pagó)'

    caja_turno = models.ForeignKey(CajaTurno, on_delete=models.PROTECT, related_name='pagos')
    comanda = models.ForeignKey(Comanda, on_delete=models.PROTECT, related_name='pagos')
    lineas_pagadas = models.ManyToManyField('comandas.LineaComanda', related_name='pagos', blank=True)
    metodo_pago = models.ForeignKey(MetodoPago, on_delete=models.PROTECT, related_name='pagos')
    monto = models.DecimalField(max_digits=12, decimal_places=2)
    vuelto = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    referencia = models.CharField(max_length=100, blank=True, null=True)
    transaccion_id = models.CharField(max_length=50, blank=True, null=True,
                                      help_text="ID único para agrupar pagos de una misma transacción")
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.PAGADO)
    fecha_pago = models.DateTimeField(auto_now_add=True)
    observacion = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'pago'
        verbose_name = 'Pago'

