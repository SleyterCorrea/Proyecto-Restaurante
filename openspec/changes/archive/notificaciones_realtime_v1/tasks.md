# Tasks: Implementación de WebSockets

## Fase 1: Infraestructura
- [x] Instalar dependencias: `pip install channels daphne`
- [x] Configurar `settings.py`:
  - [x] Añadir `daphne` a `INSTALLED_APPS` (debe ser la primera).
  - [x] Añadir `channels` a `INSTALLED_APPS`.
  - [x] Configurar `ASGI_APPLICATION`.
  - [x] Configurar `CHANNEL_LAYERS` (InMemory).
- [x] Crear `restaurant/asgi.py`.

## Fase 2: Lógica WebSocket
- [x] Crear app `apps.notificaciones`.
- [x] Definir `NotificationConsumer` en `apps/notificaciones/consumers.py`.
- [x] Definir rutas de WebSocket en `apps/notificaciones/routing.py`.
- [x] Integrar rutas en `restaurant/asgi.py`.

## Fase 3: Disparadores de Notificación
- [x] Crear `apps/notificaciones/signals.py`.
- [x] Conectar el signal `post_save` de `LineaComanda`.
- [x] Implementar la función `enviar_notificacion_plato_listo`.

## Fase 4: Frontend
- [x] Implementar sistema de Toasts en `templates/base.html`.
- [x] Añadir script de conexión WebSocket en `templates/base.html`.
- [x] Probar la recepción de mensajes.
