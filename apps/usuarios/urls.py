from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView
from .views import LoginView, UsuarioProfileView, api_toggle_tema, UsuarioViewSet, RolListView, api_consultar_reniec

router = DefaultRouter()
router.register(r'trabajadores', UsuarioViewSet, basename='trabajador')

urlpatterns = [
    path('auth/login/', LoginView.as_view(), name='token_obtain_pair'),
    path('auth/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('auth/me/', UsuarioProfileView.as_view(), name='user_profile'),
    path('configuracion/toggle-tema/', api_toggle_tema, name='toggle_tema'),
    path('reniec/consultar/', api_consultar_reniec, name='reniec_consultar'),
    path('roles/', RolListView.as_view(), name='rol_list'),
    path('', include(router.urls)),
]
