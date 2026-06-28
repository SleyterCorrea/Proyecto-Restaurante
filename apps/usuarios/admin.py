from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Rol, Usuario

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
