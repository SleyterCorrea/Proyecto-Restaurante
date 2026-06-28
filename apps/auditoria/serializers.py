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
            'rol',
            'modulo',
            'codigo_evento',
            'severidad',
            'estado_resultado',
            'accion',
            'entidad',
            'entidad_id',
            'descripcion',
            'motivo',
            'detalle_anterior',
            'detalle_nuevo',
            'impacto_economico_estimado',
            'ip',
            'user_agent',
            'ruta',
            'metodo_http',
            'estado_revision',
        ]
