from rest_framework import serializers

from .models import AuditLog


class AuditLogSerializer(serializers.ModelSerializer):
    usuario = serializers.ReadOnlyField(source='usuario.username')
    responsable_revision = serializers.ReadOnlyField(
        source='responsable_revision.username'
    )
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
            'responsable_revision',
            'alerta_activa',
            'clave_alerta',
        ]


class AuditLogDetailSerializer(AuditLogSerializer):
    class Meta(AuditLogSerializer.Meta):
        fields = AuditLogSerializer.Meta.fields + [
            'created_at',
            'updated_at',
        ]


class AuditLogFilterOptionsSerializer(serializers.Serializer):
    usuarios = serializers.ListField(child=serializers.DictField(), read_only=True)
    roles = serializers.ListField(child=serializers.CharField(), read_only=True)
    modulos = serializers.ListField(child=serializers.CharField(), read_only=True)
    severidades = serializers.ListField(child=serializers.CharField(), read_only=True)
    tipos_evento = serializers.ListField(child=serializers.CharField(), read_only=True)
    entidades = serializers.ListField(child=serializers.CharField(), read_only=True)
    estados_revision = serializers.ListField(child=serializers.CharField(), read_only=True)
    responsables_revision = serializers.ListField(child=serializers.DictField(), read_only=True)
