from django.contrib import admin

from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = [
        'fecha_evento',
        'usuario',
        'rol',
        'codigo_evento',
        'modulo',
        'severidad',
        'estado_resultado',
        'entidad',
        'entidad_id',
        'estado_revision',
        'responsable_revision',
        'alerta_activa',
    ]
    list_filter = [
        'modulo',
        'codigo_evento',
        'severidad',
        'estado_resultado',
        'entidad',
        'estado_revision',
        'responsable_revision',
        'alerta_activa',
    ]
    search_fields = [
        'usuario__username',
        'codigo_evento',
        'entidad',
        'descripcion',
        'motivo',
        'responsable_revision__username',
    ]
    date_hierarchy = 'fecha_evento'
    readonly_fields = [
        'fecha_evento',
        'created_at',
        'updated_at',
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
        'responsable_revision',
        'alerta_activa',
        'clave_alerta',
    ]
