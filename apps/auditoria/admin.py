from django.contrib import admin

from .models import AuditLog


class AuditLogAdmin(admin.ModelAdmin):
    list_display = ['fecha_evento', 'usuario', 'accion', 'entidad', 'entidad_id']
    list_filter = ['accion', 'entidad']
    readonly_fields = [
        'fecha_evento',
        'usuario',
        'accion',
        'entidad',
        'entidad_id',
        'detalle_anterior',
        'detalle_nuevo',
        'ip',
        'user_agent',
    ]


# El registro se activara cuando el modulo sea dueno definitivo del modelo
# para evitar duplicarlo mientras apps.usuarios siga siendo el origen real.

