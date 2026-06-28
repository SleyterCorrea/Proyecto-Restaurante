from rest_framework import serializers

from .models import AuditLog


class AuditLogSerializer(serializers.ModelSerializer):
    usuario = serializers.ReadOnlyField(source='usuario.username')
    fecha = serializers.DateTimeField(source='fecha_evento', format='%Y-%m-%d %H:%M:%S', read_only=True)

    class Meta:
        model = AuditLog
        fields = [
            'id',
            'fecha',
            'usuario',
            'accion',
            'entidad',
            'entidad_id',
            'detalle_anterior',
            'detalle_nuevo',
            'ip',
            'user_agent',
        ]

