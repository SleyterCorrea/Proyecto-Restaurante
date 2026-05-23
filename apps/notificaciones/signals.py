from django.db.models.signals import post_save
from django.dispatch import receiver
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from apps.comandas.models import LineaComanda

@receiver(post_save, sender=LineaComanda)
def notificar_plato_listo(sender, instance, created, **kwargs):
    """
    Dispara una notificación por WebSocket cuando una línea de comanda
    cambia su estado a 'LISTO'.
    """
    # Solo nos interesa si el estado es LISTO
    print(f"SIGNAL FIRED for LineaComanda {instance.id}, estado: {instance.estado}", flush=True)
    if instance.estado == 'LISTO':
        print(f"LineaComanda {instance.id} is LISTO. Sending websocket message...", flush=True)
        # Evitar notificaciones duplicadas si ya estaba listo (opcional, 
        # pero post_save se dispara en cada guardado).
        # En un sistema real, compararíamos con el valor previo.
        
        channel_layer = get_channel_layer()
        mesa_numero = instance.comanda.mesa.numero
        cliente = instance.comanda.nombre_cliente or "Cliente"
        plato_nombre = instance.plato.nombre
        
        try:
            async_to_sync(channel_layer.group_send)(
                "notificaciones_mozos",
                {
                    "type": "notify_ready",
                    "mesa": mesa_numero,
                    "cliente": cliente,
                    "plato": plato_nombre,
                }
            )
        except Exception as e:
            # Tolerancia a fallos: Evitar que fallas del WebSocket (e.g., caídas de Redis)
            # rompan la transacción principal en la base de datos de Django.
            print(f"Error al enviar notificación WebSocket (notificar_plato_listo): {e}", flush=True)
