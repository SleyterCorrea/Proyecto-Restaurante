# Propuesta: Notificaciones en Tiempo Real (WebSockets)

## Problema
Actualmente, los mozos deben revisar manualmente el estado de los platos o esperar a que se actualice la pantalla para saber si un pedido está listo. No existe un mecanismo de alerta proactivo que les avise en el momento exacto en que la cocina termina un plato.

## Solución Propuesta
Implementar un sistema de notificaciones push utilizando **WebSockets** (Django Channels). 
- Cuando un cocinero marca un plato como **LISTO**, el backend enviará un mensaje por WebSocket a un grupo específico de mozos.
- El frontend (mozos) recibirá el mensaje y mostrará una notificación visual (Toast) y sonora (opcional).

## Arquitectura
1. **Daphne**: Servidor ASGI para manejar WebSockets.
2. **Django Channels**: Framework para manejar la lógica de comunicación asíncrona.
3. **Channel Layer (In-Memory)**: Para intercomunicación entre procesos (se recomienda Redis en producción).
4. **Group Notification**: Grupo `notificaciones_mozos` donde se suscriben todos los mozos activos.

## Impacto
- **Backend**: Instalación de `channels` y `daphne`. Configuración de `asgi.py` y `settings.py`.
- **Comandas**: Trigger en el cambio de estado de `LineaComanda`.
- **Frontend**: Listener global en `base.html` para recibir alertas.

## Plan de Rollback
Desactivar `channels` de `INSTALLED_APPS` y revertir `asgi.py` a su estado original (o seguir usando WSGI).
