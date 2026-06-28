from django.urls import path

from . import views


app_name = 'auditoria'

urlpatterns = [
    path('auditoria/', views.admin_auditoria, name='admin_auditoria'),
    path('api/auditoria-logs/', views.api_auditoria_logs, name='api_auditoria_logs'),
]

