import json
from channels.generic.websocket import AsyncJsonWebsocketConsumer


class KDSConsumer(AsyncJsonWebsocketConsumer):
    """
    WebSocket consumer para el Kitchen Display System.

    Patrón híbrido:
    - El consumer solo envía señales de "hay cambios, refresca".
    - El frontend hace un GET HTTP para obtener los datos actualizados.
    - Esto simplifica la lógica y reutiliza los endpoints REST existentes.
    """

    KDS_GROUP = 'kds_updates'

    async def connect(self):
        """Acepta la conexión si el usuario está autenticado."""
        user = self.scope.get('user')
        if user and user.is_authenticated:
            await self.channel_layer.group_add(
                self.KDS_GROUP,
                self.channel_name,
            )
            await self.accept()
            await self.send_json({
                'type': 'connection_established',
                'message': 'Conectado al KDS en tiempo real',
            })
        else:
            await self.close()

    async def disconnect(self, close_code):
        """Sale del grupo al desconectar."""
        await self.channel_layer.group_discard(
            self.KDS_GROUP,
            self.channel_name,
        )

    async def receive_json(self, content, **kwargs):
        """
        Recibe mensajes del frontend.
        Solo acepta pings para mantener la conexión viva.
        """
        msg_type = content.get('type', '')
        if msg_type == 'ping':
            await self.send_json({'type': 'pong'})

    # ========= GROUP HANDLERS =========

    async def kds_update(self, event):
        """
        Handler cuando el backend emite un evento de actualización.
        Envía la señal al frontend para que refresque via HTTP.
        """
        await self.send_json({
            'type': 'kds_update',
            'action': event.get('action', 'refresh'),
            'detail': event.get('detail', {}),
        })
