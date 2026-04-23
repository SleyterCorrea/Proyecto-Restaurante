"""
URL Configuration raíz del proyecto restaurant.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views
from django.shortcuts import redirect

urlpatterns = [
    path('admin/', admin.site.urls),

    # ── Raíz → redirigir al plano ─────────────────────────────────────────────
    path('', lambda req: redirect('/mesero/mesas/')),

    # ── Autenticación ─────────────────────────────────────────────────────────
    path('login/',  auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='/login/'), name='logout'),

    # ── Vistas del módulo mesero (HTML) ──────────────────────────────────────
    path('mesero/', include('apps.mesas.urls')),
    path('mesero/', include('apps.comandas.urls')),

    # ── API REST interna ──────────────────────────────────────────────────────
    path('api/mesas/',    include('apps.mesas.api_urls')),
    path('api/menu/',     include('apps.menu.api_urls')),
    path('api/comandas/', include('apps.comandas.api_urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
