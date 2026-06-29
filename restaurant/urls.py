from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views
from apps.usuarios.views import DashboardRedirectView, DocumentacionView, LoginWebView
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView

urlpatterns = [
    path('admin/', admin.site.urls),

    # ── Raíz → redirigir según Rol ───────────────────────────────────────────
    path('', DashboardRedirectView.as_view(), name='index'),

    # ── Autenticación ─────────────────────────────────────────────────────────
    path('login/', LoginWebView.as_view(), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='/login/'), name='logout'),

    # ── Vistas de los módulos (HTML) ─────────────────────────────────────────
    path('mesero/', include('apps.mesas.urls')),
    path('mesero/', include('apps.comandas.urls')),
    path('admin-panel/', include('apps.reportes.urls')),
    
    path('cocina/', include('apps.comandas.urls_cocina')),
    path('caja/', include('apps.caja.urls')),

    # ── Documentación ────────────────────────────────────────────────────────
    path('documentacion/', DocumentacionView.as_view(), name='documentacion'),

    # ── API REST ─────────────────────────────────────────────────────────────
    path('api/',            include('apps.usuarios.urls')),
    path('api/mesas/',      include('apps.mesas.api_urls')),
    path('api/menu/',       include('apps.menu.api_urls')),
    path('api/comandas/',   include('apps.comandas.api_urls')),
    path('api/inventario/', include('apps.inventario.urls')),
    
    # ── KDS APIs (Phase 4) ───────────────────────────────────────────────────
    path('api/cocina/',     include('apps.comandas.api_cocina_urls')),
    path('api/lineas/',     include('apps.comandas.api_lineas_urls')),

    # ── Documentación API (Swagger) ──────────────────────────────────────────
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),

] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
