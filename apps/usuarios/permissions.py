from rest_framework import permissions

class EsRolBase(permissions.BasePermission):
    """Clase base para permisos por rol."""
    rol_requerido = None

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return request.user.rol.nombre == self.rol_requerido

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
        if not request.user or not request.user.is_authenticated:
            return False
        return request.user.rol.nombre in ['MOZO', 'ADMIN']

class EsCocineroOAdmin(permissions.BasePermission):
    """Permiso para Cocinero o Administrador."""
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return request.user.rol.nombre in ['COCINERO', 'ADMIN']

class EsCajeroOAdmin(permissions.BasePermission):
    """Permiso para Cajero o Administrador."""
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return request.user.rol.nombre in ['CAJERO', 'ADMIN']
