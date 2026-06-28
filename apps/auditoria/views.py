from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.usuarios.decorators import rol_requerido
from apps.usuarios.permissions import EsAdmin

from .serializers import AuditLogSerializer
from .services import AuditoriaService


@login_required
@rol_requerido('ADMIN')
def admin_auditoria(request):
    return render(request, 'admin_panel/auditoria.html')


@api_view(['GET'])
@permission_classes([EsAdmin])
def api_auditoria_logs(request):
    search = request.GET.get('search', '').strip()
    entidad = request.GET.get('entidad', '').strip()
    accion = request.GET.get('accion', '').strip()
    modulo = request.GET.get('modulo', '').strip()
    severidad = request.GET.get('severidad', '').strip()
    estado_revision = request.GET.get('estado_revision', '').strip()

    logs = AuditoriaService.listar_logs(
        search=search,
        entidad=entidad,
        accion=accion,
        modulo=modulo,
        severidad=severidad,
        estado_revision=estado_revision,
    )[:500]
    serializer = AuditLogSerializer(logs, many=True)
    return Response(serializer.data)
