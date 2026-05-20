import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from django.urls import re_path
from apps.notificaciones.routing import websocket_urlpatterns as notif_ws
from apps.comandas.consumers import KDSConsumer

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'restaurant.settings')

# Combinar WebSocket routes de notificaciones y KDS
all_ws_patterns = notif_ws + [
    re_path(r'^ws/cocina/kds/$', KDSConsumer.as_asgi()),
]

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": AuthMiddlewareStack(
        URLRouter(
            all_ws_patterns
        )
    ),
})

