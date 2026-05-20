from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Rol, Usuario, AuditLog

@admin.register(Rol)
class RolAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'descripcion', 'activo']

@admin.register(Usuario)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'rol', 'nombres', 'apellidos', 'is_staff')
    list_filter = ('rol', 'is_staff', 'is_superuser', 'is_active')
    fieldsets = UserAdmin.fieldsets + (
        ('Información Extra', {'fields': ('rol', 'nombres', 'apellidos', 'telefono', 'activo')}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Información Extra', {'fields': ('rol', 'nombres', 'apellidos', 'email', 'telefono', 'activo')}),
    )

@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ['fecha_evento', 'usuario', 'accion', 'entidad', 'entidad_id']
    list_filter = ['accion', 'entidad']
    readonly_fields = ['fecha_evento', 'usuario', 'accion', 'entidad', 'entidad_id', 'detalle_anterior', 'detalle_nuevo', 'ip', 'user_agent']
