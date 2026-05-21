import logging

from django.db import transaction
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from .models import Insumo, RecetaInsumo
from .services import actualizar_disponibilidad_platos, notificar_stock_critico_si_aplica

logger = logging.getLogger(__name__)


@receiver(pre_save, sender=Insumo)
def _stash_stock_anterior(sender, instance, **kwargs):
    """Guarda el stock previo para detectar cruce del umbral en post_save."""
    if instance.pk:
        try:
            anterior = sender.objects.only('stock_real', 'stock_minimo').get(pk=instance.pk)
            instance._stock_real_anterior = anterior.stock_real
            instance._stock_minimo_anterior = anterior.stock_minimo
        except sender.DoesNotExist:
            instance._stock_real_anterior = None
            instance._stock_minimo_anterior = None
    else:
        instance._stock_real_anterior = None
        instance._stock_minimo_anterior = None


@receiver(post_save, sender=Insumo)
def auto_desactivar_platos(sender, instance, created=False, update_fields=None, **kwargs):
    """
    Cuando un insumo cambia su stock o estado activo, actualiza disponibilidad de platos.
    Si cruzó la línea OK → BAJO/AGOTADO, dispara alerta por email a admins.

    Nota: bulk_update() no dispara post_save por defecto. Si un script o vista
    necesita saltar este recalculo al usar save() individual, debe proveer un
    update_fields que no incluya 'stock_real', 'activo' o 'stock_minimo'.
    """
    if created:
        return

    # Solo recalcular si cambió stock_real, activo o stock_minimo
    campos_relevantes = {'stock_real', 'activo', 'stock_minimo'}
    if update_fields is not None and not campos_relevantes.intersection(set(update_fields)):
        return

    actualizar_disponibilidad_platos(instance)
    logger.debug("Disponibilidad actualizada para insumo '%s'", instance.nombre)

    # ¿Cruzó el umbral hacia bajo/agotado en este save?
    anterior = getattr(instance, '_stock_real_anterior', None)
    minimo_ant = getattr(instance, '_stock_minimo_anterior', instance.stock_minimo)
    if anterior is None:
        return

    estaba_ok = anterior > minimo_ant
    ahora_critico = instance.stock_real <= instance.stock_minimo
    if estaba_ok and ahora_critico:
        # Diferir al commit para no enviar email en transacciones que pueden hacer rollback
        transaction.on_commit(lambda: notificar_stock_critico_si_aplica(instance))


@receiver(post_save, sender=RecetaInsumo)
def actualizar_plato_al_cambiar_receta(sender, instance, **kwargs):
    """Cuando se agrega/edita una receta, verifica la disponibilidad del plato."""
    actualizar_disponibilidad_platos(instance.insumo)
    logger.debug("Disponibilidad verificada para plato '%s'", instance.plato.nombre)
