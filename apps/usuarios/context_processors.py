from apps.usuarios.models import ConfiguracionSistema

def config_global(request):
    """
    Context processor que inyecta la configuración global (ej. tema_oscuro)
    en todas las plantillas de Django.
    """
    try:
        config = ConfiguracionSistema.get_instancia()
        return {'config_global': config}
    except Exception:
        # En caso de que la DB aún no haya migrado o falle, por defecto es True
        return {'config_global': {'tema_oscuro': True}}
