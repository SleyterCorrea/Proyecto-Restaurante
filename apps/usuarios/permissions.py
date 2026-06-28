from rest_framework import permissions

from .services import UsuarioService


def _tiene_rol(request, view, roles):
    if not request.user or not request.user.is_authenticated:
        return False
    permitido = request.user.rol.nombre in roles
    if not permitido:
        UsuarioService.registrar_acceso_denegado(
            request.user,
            request=request,
            recurso=getattr(view, '__class__', type(view)).__name__,
        )
    return permitido

class EsRolBase(permissions.BasePermission):
    """Clase base para permisos por rol."""
    rol_requerido = None

    def has_permission(self, request, view):
        return _tiene_rol(request, view, [self.rol_requerido])

class EsAdmin(EsRolBase):
    rol_requerido = 'ADMIN'

class EsMozo(EsRolBase):
    rol_requerido = 'MOZO'

class EsCocinero(EsRolBase):
    rol_requerido = 'COCINERO'

class EsCajero(EsRolBase):
    rol_requerido = 'CAJERO'

class EsMozoOAdmin(permissions.BasePermission):
    """Permiso para Mozo o Administrador."""
    def has_permission(self, request, view):
        return _tiene_rol(request, view, ['MOZO', 'ADMIN'])

class EsCocineroOAdmin(permissions.BasePermission):
    """Permiso para Cocinero o Administrador."""
    def has_permission(self, request, view):
        return _tiene_rol(request, view, ['COCINERO', 'ADMIN'])

class EsCajeroOAdmin(permissions.BasePermission):
    """Permiso para Cajero o Administrador."""
    def has_permission(self, request, view):
        return _tiene_rol(request, view, ['CAJERO', 'ADMIN'])
