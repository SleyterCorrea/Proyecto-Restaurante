from django.urls import path
from . import views

from apps.usuarios.views import GestionTrabajadoresView

urlpatterns = [
    # Vistas HTML
    path('', views.admin_reportes, name='admin_index'),
    path('dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('inventario/', views.admin_inventario, name='admin_inventario'),
    path('menu/', views.admin_menu, name='admin_menu'),
    path('recetas/', views.admin_recetas, name='admin_recetas'),
    path('reportes/', views.admin_reportes, name='admin_reportes'),
    path('trabajadores/', GestionTrabajadoresView.as_view(), name='admin_trabajadores'),
    path('auditoria/', views.admin_auditoria, name='admin_auditoria'),


    # API Endpoints
    path('api/ventas-turno/', views.api_ventas_turno, name='api_ventas_turno'),
    path('api/top-platos/', views.api_top_platos, name='api_top_platos'),
    path('api/ventas-por-hora/', views.api_ventas_por_hora, name='api_ventas_por_hora'),
    path('api/ventas-historial/', views.api_ventas_historial, name='api_ventas_historial'),
    path('api/auditoria-logs/', views.api_auditoria_logs, name='api_auditoria_logs'),
    path('api/exportar-csv/', views.api_exportar_csv, name='api_exportar_csv'),
]
