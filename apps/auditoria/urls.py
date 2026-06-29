from django.urls import path

from . import views


app_name = 'auditoria'

urlpatterns = [
    path('auditoria/', views.admin_auditoria, name='admin_auditoria'),
    path('api/auditoria-logs/', views.api_auditoria_logs, name='api_auditoria_logs'),
    path('api/auditoria-logs/filtros/', views.api_auditoria_filtros, name='api_auditoria_filtros'),
    path('api/auditoria-logs/export/', views.api_auditoria_exportar, name='api_auditoria_exportar'),
    path('api/auditoria-logs/<int:log_id>/', views.api_auditoria_log_detalle, name='api_auditoria_log_detalle'),
    path('api/auditoria-logs/<int:log_id>/revision/', views.api_auditoria_log_revision, name='api_auditoria_log_revision'),
]
