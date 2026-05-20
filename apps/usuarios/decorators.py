from django.shortcuts import redirect
from django.contrib import messages
from functools import wraps

def rol_requerido(*roles_permitidos):
    """
    Decorador para vistas HTML que verifica el rol del usuario.
    Si no tiene permiso, redirige a su dashboard principal.
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('login')
            
            rol_actual = request.user.rol.nombre
            if rol_actual in roles_permitidos or rol_actual == 'ADMIN':
                return view_func(request, *args, **kwargs)
            
            # Si no tiene permiso, mensaje de error y redirección
            messages.error(request, f"Acceso denegado: No tenés permiso para acceder a esta sección.")
            
            # Redirigir según su propio rol (usando la lógica del DashboardRedirectView)
            if rol_actual == 'COCINERO':
                return redirect('/cocina/kds/')
            elif rol_actual == 'CAJERO':
                return redirect('/caja/cobrar/')
            elif rol_actual == 'MOZO':
                return redirect('/mesero/mesas/')
            else:
                return redirect('index')
                
        return _wrapped_view
    return decorator
