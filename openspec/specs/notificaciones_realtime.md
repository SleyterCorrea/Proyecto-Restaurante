# Especificación: Notificaciones en Tiempo Real (Kitchen-to-Waiter)

## 1. Problema y Objetivo
**Problema**: Los mozos debían revisar manualmente o por polling constante si la cocina había terminado un pedido, lo que generaba latencia en el servicio y carga innecesaria en el servidor.
**Objetivo**: Implementar un sistema de notificaciones "Push" utilizando WebSockets para que el mozo reciba una alerta instantánea (Toast) en el momento exacto en que un plato es marcado como `LISTO` en el KDS.

## 2. Arquitectura Técnica

El flujo de datos sigue un modelo de eventos asíncronos:

1. **Trigger (Signal)**: Cuando se actualiza una `LineaComanda` a estado `LISTO`, un `post_save` signal en Django captura el evento.
2. **Channel Layer (Redis)**: La señal utiliza `async_to_sync` para enviar un mensaje al grupo de WebSockets `"notificaciones_mozos"`. Se utiliza Redis como Broker para garantizar la comunicación entre procesos (IPC) entre los workers de Django y el servidor ASGI.
3. **Consumer (Daphne)**: El `NotificationConsumer` (asíncrono) recibe el evento del grupo y lo retransmite a todos los clientes conectados.
4. **Frontend (Alpine.js)**: Un componente global en `base.html` mantiene la conexión activa y despliega notificaciones flotantes (Toasts) al recibir el mensaje.

## 3. Infraestructura Requerida

Para que este sistema funcione, el entorno debe contar con:
- **Servidor ASGI (Daphne)**: Reemplaza al WSGI estándar para manejar conexiones persistentes.
- **Protocol Server (Channels)**: Integración de Django Channels 4.0+.
- **Broker (Redis)**: Contenedor `restaurant_redis` dedicado para la gestión de capas de canales.

## 4. Componentes Clave

### Backend
- **App**: `apps.notificaciones`
- **Consumer**: `NotificationConsumer` en `consumers.py`. Maneja el handshake y la suscripción a grupos.
- **Signals**: `notificar_plato_listo` en `signals.py`. Filtra transiciones de estado a `LISTO`.

### Frontend
- **Listener**: Implementado en `templates/base.html` usando Alpine.js.
- **Componente**: `notificacionesGlobal`. Maneja reconexión automática y el array de `toasts` activos.
- **Estética**: Notificaciones estilo Glassmorphism con colores adaptativos según el tema activo.

## 5. Consideraciones de Seguridad
- El acceso al WebSocket está restringido a usuarios autenticados.
- Las notificaciones son de solo lectura (el cliente no envía comandos sensibles por este canal).

---
*Documentación creada como parte del Sprint de WebSockets.*
