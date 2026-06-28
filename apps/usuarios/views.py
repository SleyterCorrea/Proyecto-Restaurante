from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework import generics, permissions
from apps.auditoria.models import AuditLog
from apps.auditoria.services import AuditoriaService
from .models import Usuario
from .serializers import UsuarioSerializer, CustomTokenObtainPairSerializer
import urllib.request
import urllib.parse
import json as _json

class LoginView(TokenObtainPairView):
    """Vista de login personalizada que usa el serializer con claims extendidos."""
    serializer_class = CustomTokenObtainPairSerializer

class UsuarioProfileView(generics.RetrieveAPIView):
    """Vista para obtener el perfil del usuario autenticado."""
    serializer_class = UsuarioSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user

from django.views.generic import RedirectView
from django.contrib.auth.mixins import LoginRequiredMixin

class DashboardRedirectView(LoginRequiredMixin, RedirectView):
    """Redirige al dashboard correspondiente según el rol del usuario."""
    permanent = False

    def get_redirect_url(self, *args, **kwargs):
        rol = self.request.user.rol.nombre
        if rol == 'ADMIN':
            return '/admin-panel/reportes/'
        elif rol == 'COCINERO':
            return '/cocina/kds/'
        elif rol == 'CAJERO':
            return '/caja/cobrar/'
        else: # MOZO
            return '/mesero/mesas/'

from django.views.generic import TemplateView

class DocumentacionView(LoginRequiredMixin, TemplateView):
    """Vista que renderiza la documentación del sistema según el rol del usuario."""
    template_name = 'documentacion.html'

from rest_framework import viewsets
from .models import Rol
from .serializers import RolSerializer

class UsuarioViewSet(viewsets.ModelViewSet):
    """ViewSet para la gestión de trabajadores (CRUD)."""
    queryset = Usuario.objects.all().order_by('-created_at')
    serializer_class = UsuarioSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if self.request.user.rol.nombre == 'ADMIN':
            return Usuario.objects.all().order_by('-created_at')
        return Usuario.objects.filter(id=self.request.user.id)

    def perform_create(self, serializer):
        instance = serializer.save()
        AuditoriaService.registrar(
            usuario=self.request.user,
            accion='USUARIO_CREADO',
            modulo='USUARIOS',
            entidad='USUARIO',
            entidad_id=instance.id,
            severidad=AuditLog.Severidad.INFO,
            estado_resultado=AuditLog.EstadoResultado.EXITOSO,
            descripcion=f'Se creo el usuario {instance.username}.',
            valores_nuevos=serializer.data,
            request=self.request,
        )

    def perform_update(self, serializer):
        old_instance = self.get_object()
        old_rol = old_instance.rol.nombre
        old_activo = old_instance.activo
        password_modificado = bool(serializer.validated_data.get('password'))
        instance = serializer.save()

        if old_rol != instance.rol.nombre:
            escalamiento = old_rol != 'ADMIN' and instance.rol.nombre == 'ADMIN'
            AuditoriaService.registrar(
                usuario=self.request.user,
                accion=(
                    'USUARIO_ESCALAMIENTO_PRIVILEGIOS'
                    if escalamiento
                    else 'USUARIO_ROL_MODIFICADO'
                ),
                modulo='USUARIOS',
                entidad='USUARIO',
                entidad_id=instance.id,
                severidad=(
                    AuditLog.Severidad.CRITICA
                    if escalamiento
                    else AuditLog.Severidad.ADVERTENCIA
                ),
                estado_resultado=AuditLog.EstadoResultado.EXITOSO,
                descripcion=(
                    f'El rol de {instance.username} cambio de '
                    f'{old_rol} a {instance.rol.nombre}.'
                ),
                valores_anteriores={'rol': old_rol},
                valores_nuevos={'rol': instance.rol.nombre},
                request=self.request,
            )

        if old_activo != instance.activo:
            AuditoriaService.registrar(
                usuario=self.request.user,
                accion=(
                    'USUARIO_REACTIVADO'
                    if instance.activo
                    else 'USUARIO_DESACTIVADO'
                ),
                modulo='USUARIOS',
                entidad='USUARIO',
                entidad_id=instance.id,
                severidad=AuditLog.Severidad.ADVERTENCIA,
                estado_resultado=AuditLog.EstadoResultado.EXITOSO,
                descripcion=f'Se cambio el estado activo de {instance.username}.',
                valores_anteriores={'activo': old_activo},
                valores_nuevos={'activo': instance.activo},
                request=self.request,
            )

        if password_modificado:
            AuditoriaService.registrar(
                usuario=self.request.user,
                accion='USUARIO_PASSWORD_MODIFICADO',
                modulo='USUARIOS',
                entidad='USUARIO',
                entidad_id=instance.id,
                severidad=AuditLog.Severidad.ADVERTENCIA,
                estado_resultado=AuditLog.EstadoResultado.EXITOSO,
                descripcion=f'Se modifico la clave de {instance.username}.',
                valores_anteriores={'password': 'PROTEGIDO'},
                valores_nuevos={'password': 'PROTEGIDO'},
                request=self.request,
            )

    def perform_destroy(self, instance):
        instance.delete()

class RolListView(generics.ListAPIView):
    """Lista de roles para el selector del formulario."""
    queryset = Rol.objects.all()
    serializer_class = RolSerializer
    permission_classes = [permissions.IsAuthenticated]

class GestionTrabajadoresView(LoginRequiredMixin, TemplateView):
    """Vista principal para el panel de gestión de trabajadores (Solo Admin)."""
    template_name = 'admin_panel/trabajadores.html'

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated or request.user.rol.nombre != 'ADMIN':
            return self.handle_no_permission()
        return super().dispatch(request, *args, **kwargs)

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from .models import ConfiguracionSistema
import json

@csrf_exempt
@login_required
def api_toggle_tema(request):
    """
    Endpoint para alternar entre modo claro y oscuro.
    Puede ser ejecutado por usuarios con rol ADMIN o MOZO.
    """
    if request.method == 'POST':
        if request.user.rol.nombre not in ['ADMIN', 'MOZO']:
            return JsonResponse({'ok': False, 'error': 'No tienes permisos para cambiar el tema global.'}, status=403)
        
        config = ConfiguracionSistema.get_instancia()
        # Alternar
        config.tema_oscuro = not config.tema_oscuro
        config.save()
        
        return JsonResponse({'ok': True, 'tema_oscuro': config.tema_oscuro})
    
    return JsonResponse({'ok': False, 'error': 'Método no permitido'}, status=405)


from django.conf import settings

@login_required
def api_consultar_reniec(request):
    """
    Proxy seguro para consultar datos personales via DECOLECTA (RENIEC).
    La API key permanece en el servidor y nunca se expone al cliente.
    Solo accesible por usuarios ADMIN autenticados.
    """
    if request.user.rol.nombre != 'ADMIN':
        return JsonResponse({'ok': False, 'error': 'Sin permisos.'}, status=403)

    dni = request.GET.get('dni', '').strip()
    if not dni or len(dni) != 8 or not dni.isdigit():
        return JsonResponse({'ok': False, 'error': 'DNI inválido. Debe tener 8 dígitos.'}, status=400)

    api_key = getattr(settings, 'DECOLECTA_API_KEY', '')
    base_url = getattr(settings, 'DECOLECTA_BASE_URL', 'https://api.decolecta.com/v1/reniec/dni')

    if not api_key:
        return JsonResponse({'ok': False, 'error': 'API Key de DECOLECTA no configurada.'}, status=500)

    url = f'{base_url}?numero={urllib.parse.quote(dni)}'

    try:
        req = urllib.request.Request(
            url,
            headers={
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json',
            }
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = _json.loads(resp.read().decode())

        return JsonResponse({
            'ok': True,
            'nombres': data.get('first_name', '').title(),
            'apellidos': f"{data.get('first_last_name', '')} {data.get('second_last_name', '')}".strip().title(),
            'dni': data.get('document_number', dni),
        })

    except urllib.error.HTTPError as e:
        code = e.code
        if code == 404:
            return JsonResponse({'ok': False, 'error': 'DNI no encontrado en RENIEC.'}, status=404)
        if code == 401:
            return JsonResponse({'ok': False, 'error': 'Error de autenticación con DECOLECTA.'}, status=502)
        return JsonResponse({'ok': False, 'error': f'Error externo: HTTP {code}'}, status=502)
    except Exception as exc:
        return JsonResponse({'ok': False, 'error': f'No se pudo conectar con RENIEC: {str(exc)}'}, status=503)
