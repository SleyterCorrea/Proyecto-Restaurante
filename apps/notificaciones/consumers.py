import json
from channels.generic.websocket import AsyncWebsocketConsumer

class NotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # Todos los mozos se unen al grupo "notificaciones_mozos"
        self.group_name = "notificaciones_mozos"
        
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )
        
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.group_name,
            self.channel_name
        )

    # Este método se llama cuando se envía un mensaje al grupo
    async def notify_ready(self, event):
        # Enviar el mensaje al WebSocket
        await self.send(text_data=json.dumps({
            'type': 'comida_lista',
            'mesa': event['mesa'],
            'cliente': event['cliente'],
            'plato': event['plato']
        }))
