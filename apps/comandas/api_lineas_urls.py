from django.urls import path
from . import views

urlpatterns = [
    # PATCH /api/lineas/<id>/estado/
    path('<int:pk>/estado/', views.api_linea_estado, name='api_linea_estado'),
    # PATCH / DELETE /api/lineas/<id>/
    path('<int:pk>/', views.api_linea_detail, name='api_linea_detail'),
]
