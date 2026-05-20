from django.urls import path
from . import views

urlpatterns = [
    path('kds/', views.kds_view, name='kds_view'),
]
