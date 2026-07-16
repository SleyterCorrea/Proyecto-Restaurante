"""Genera datos de prueba controlados para el panel de Auditoria de Riesgos.

Uso:
    python manage.py seed_auditoria_demo            # crea los datos demo (idempotente)
    python manage.py seed_auditoria_demo --reset-demo   # elimina SOLO los datos demo
    python manage.py seed_auditoria_demo --force        # fuerza ejecucion si DEBUG=False

Seguridad:
    - Solo se ejecuta con DEBUG=True (salvo --force, para entornos controlados).
    - Cada registro demo se marca con clave_alerta='DEMO_AUDITORIA' y la
      descripcion lleva el prefijo '[DEMO_AUDITORIA] '. La limpieza elimina
      UNICAMENTE esos registros; nunca toca datos reales del sistema.
    - No se generan acciones inexistentes ni operativas descartadas (no se crea
      AUDITORIA_ACCESO_PANEL ni ningun evento del modulo MESAS).
"""
from decimal import Decimal

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.auditoria.constants import (
    ACCIONES_AUDITABLES,
    ACCIONES_CON_MOTIVO_OBLIGATORIO,
)
from apps.auditoria.models import AuditLog
from apps.auditoria.services import AuditoriaService
from apps.usuarios.models import Usuario


DEMO_CLAVE = 'DEMO_AUDITORIA'
DEMO_PREFIX = '[DEMO_AUDITORIA] '

# Acceso normal del administrador al panel: operacion esperada, no es riesgo.
# Se excluye deliberadamente del set de datos demo.
ACCIONES_EXCLUIDAS = {'AUDITORIA_ACCESO_PANEL'}

# Severidad: prioriza como CRITICA perdidas, anulaciones sensibles, descuadres,
# acceso denegado, escalamiento de privilegios y cambios criticos de negocio.
SEVERIDAD_CRITICA = {
    'COMANDA_PLATO_ANULADO_POST_COCINA',
    'COMANDA_ANULADA_CON_PRODUCCION',
    'CAJA_DESCUADRE_DETECTADO',
    'CAJA_CIERRE_FORZADO',
    'CAJA_VENTA_PERDIDA_REGISTRADA',
    'PAGO_ANULADO',
    'INVENTARIO_MERMA_ELEVADA',
    'INVENTARIO_EGRESO_INCOHERENTE',
    'INVENTARIO_AJUSTE_MANUAL_ELEVADO',
    'PLATO_CAMBIO_MASIVO_PRECIOS',
    'USUARIO_ESCALAMIENTO_PRIVILEGIOS',
    'ACCESO_DENEGADO',
}
SEVERIDAD_INFO = {
    'CAJA_TURNO_ABIERTO',
    'CAJA_TURNO_CERRADO',
    'USUARIO_CREADO',
    'USUARIO_REACTIVADO',
    'PLATO_DESHABILITADO_STOCK',
    'AUDITORIA_EXPORTADA',
}

# Impacto economico estimado (S/) para eventos con perdida o riesgo financiero.
IMPACTOS = {
    'CAJA_VENTA_PERDIDA_REGISTRADA': '120.50',
    'PAGO_ANULADO': '85.00',
    'CAJA_DESCUADRE_DETECTADO': '42.30',
    'INVENTARIO_MERMA_ELEVADA': '210.00',
    'INVENTARIO_EGRESO_INCOHERENTE': '95.75',
    'INVENTARIO_AJUSTE_MANUAL_ELEVADO': '150.00',
    'INVENTARIO_COSTO_UNITARIO_VARIACION_ALTA': '60.40',
    'PLATO_PRECIO_MODIFICADO': '12.00',
    'PLATO_CAMBIO_MASIVO_PRECIOS': '300.00',
    'COMANDA_ANULADA_CON_PRODUCCION': '48.90',
    'COMANDA_PLATO_ANULADO_POST_COCINA': '18.50',
}

MOTIVOS = {
    'COMANDA_PLATO_ANULADO': 'Cliente cambio de pedido antes de coccion.',
    'COMANDA_PLATO_ANULADO_POST_COCINA': 'Plato devuelto: error de coccion ya producido.',
    'COMANDA_ANULADA': 'Mesa abandonada antes de servir.',
    'COMANDA_ANULADA_CON_PRODUCCION': 'Anulacion con produccion: cliente se retiro.',
    'PAGO_ANULADO': 'Cobro duplicado detectado por el cajero.',
    'PLATO_MODIFICADO': 'Actualizacion de datos generales del plato.',
    'PLATO_PRECIO_MODIFICADO': 'Ajuste de precio por costo de insumos.',
    'PLATO_CAMBIO_MASIVO_PRECIOS': 'Actualizacion masiva de carta por temporada.',
    'RECETA_MODIFICADA': 'Reformulacion de receta para reducir merma.',
    'RECETA_INSUMO_ELIMINADO': 'Insumo descontinuado por proveedor.',
    'CAJA_CIERRE_FORZADO': 'Cierre forzado por fin de jornada sin arqueo.',
    'CAJA_TURNO_REABIERTO': 'Reapertura por correccion de un cobro.',
    'CAJA_VENTA_PERDIDA_REGISTRADA': 'Cliente se retiro sin pagar la cuenta.',
    'PAGO_SOFT_DELETE': 'Eliminacion logica de pago anulado erroneo.',
    'PLATO_SOFT_DELETE': 'Baja logica de plato fuera de carta.',
    'INVENTARIO_AJUSTE_MANUAL_ELEVADO': 'Ajuste manual elevado tras inventario fisico.',
}

DESCRIPCIONES = {
    'COMANDA_PLATO_ANULADO': 'Se anulo un plato de la comanda antes de cocina.',
    'COMANDA_PLATO_ANULADO_POST_COCINA': 'Se anulo un plato ya producido en cocina.',
    'COMANDA_ANULADA': 'Se anulo una comanda completa.',
    'COMANDA_ANULADA_CON_PRODUCCION': 'Se anulo una comanda con produccion en curso.',
    'CAJA_TURNO_ABIERTO': 'Apertura de turno de caja.',
    'CAJA_TURNO_CERRADO': 'Cierre de turno de caja.',
    'CAJA_DESCUADRE_DETECTADO': 'Descuadre detectado en el arqueo de caja.',
    'CAJA_CIERRE_FORZADO': 'Cierre de caja forzado sin cuadre.',
    'CAJA_TURNO_REABIERTO': 'Reapertura de un turno de caja cerrado.',
    'CAJA_VENTA_PERDIDA_REGISTRADA': 'Venta registrada como perdida (no pago).',
    'PAGO_METODO_MODIFICADO': 'Se modifico el metodo de pago de un cobro.',
    'PAGO_ANULADO': 'Se anulo un pago confirmado.',
    'PAGO_SOFT_DELETE': 'Eliminacion logica de un pago.',
    'INVENTARIO_INSUMO_AGOTADO_SIN_REPOSICION': 'Insumo agotado sin reposicion oportuna.',
    'INVENTARIO_STOCK_BAJO_PERSISTENTE': 'Stock bajo persistente por varios dias.',
    'INVENTARIO_MERMA_ELEVADA': 'Merma elevada por encima del umbral.',
    'INVENTARIO_EGRESO_INCOHERENTE': 'Egreso de inventario incoherente con ventas.',
    'INVENTARIO_AJUSTE_MANUAL_ELEVADO': 'Ajuste manual de stock por monto elevado.',
    'INVENTARIO_AJUSTES_REPETIDOS': 'Ajustes manuales repetidos en corto plazo.',
    'INVENTARIO_LOTE_REPETIDO': 'Registro de lote repetido en ingresos.',
    'INVENTARIO_COSTO_UNITARIO_VARIACION_ALTA': 'Variacion alta del costo unitario.',
    'INVENTARIO_STOCK_INSUFICIENTE_REITERADO': 'Bloqueos reiterados por stock insuficiente.',
    'RECETA_MODIFICADA': 'Se modifico la receta de un plato.',
    'RECETA_INSUMO_ELIMINADO': 'Se elimino un insumo de una receta.',
    'PLATO_DESHABILITADO_STOCK': 'Plato deshabilitado por falta de stock.',
    'PLATO_REACTIVADO_SIN_STOCK': 'Plato reactivado pese a stock insuficiente.',
    'PLATO_MODIFICADO': 'Se modificaron datos generales de un plato.',
    'PLATO_PRECIO_MODIFICADO': 'Se modifico el precio de un plato.',
    'PLATO_CAMBIO_MASIVO_PRECIOS': 'Cambio masivo de precios de la carta.',
    'PLATO_SOFT_DELETE': 'Baja logica de un plato.',
    'LOGIN_FALLIDO_REITERADO': 'Intentos de inicio de sesion fallidos reiterados.',
    'USUARIO_CREADO': 'Se creo un nuevo usuario del sistema.',
    'USUARIO_ROL_MODIFICADO': 'Se modifico el rol de un usuario.',
    'USUARIO_ESCALAMIENTO_PRIVILEGIOS': 'Escalamiento de privilegios de un usuario.',
    'USUARIO_DESACTIVADO': 'Se desactivo a un usuario.',
    'USUARIO_REACTIVADO': 'Se reactivo a un usuario.',
    'USUARIO_PASSWORD_MODIFICADO': 'Se modifico la contrasena de un usuario.',
    'ACCESO_DENEGADO': 'Intento de acceso no autorizado a un recurso protegido.',
    'AUDITORIA_EXPORTADA': 'Exportacion de registros de auditoria a CSV.',
}

USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Safari/16.5',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/123.0 Safari/537.36',
]

REVISION_CICLO = [
    AuditLog.EstadoRevision.PENDIENTE,
    AuditLog.EstadoRevision.EN_REVISION,
    AuditLog.EstadoRevision.REVISADO,
    AuditLog.EstadoRevision.DESCARTADO,
]


def modulo_de(accion):
    if accion.startswith('COMANDA_'):
        return 'COMANDAS'
    if accion.startswith('CAJA_') or accion.startswith('PAGO_'):
        return 'CAJA'
    if accion.startswith('INVENTARIO_'):
        return 'INVENTARIO'
    if accion.startswith('PLATO_') or accion.startswith('RECETA_'):
        return 'MENU'
    if accion.startswith('USUARIO_') or accion.startswith('LOGIN_') or accion == 'ACCESO_DENEGADO':
        return 'USUARIOS'
    if accion.startswith('AUDITORIA_'):
        return 'AUDITORIA'
    return 'GENERAL'


def entidad_de(accion):
    if accion.startswith('COMANDA_PLATO_'):
        return 'LINEA_COMANDA'
    if accion.startswith('COMANDA_'):
        return 'COMANDA'
    if accion == 'CAJA_VENTA_PERDIDA_REGISTRADA' or accion.startswith('PAGO_'):
        return 'PAGO'
    if accion.startswith('CAJA_'):
        return 'CAJA_TURNO'
    if accion.startswith('INVENTARIO_'):
        return 'INSUMO'
    if accion.startswith('RECETA_'):
        return 'RECETA'
    if accion.startswith('PLATO_'):
        return 'PLATO'
    if accion.startswith('USUARIO_') or accion.startswith('LOGIN_') or accion == 'ACCESO_DENEGADO':
        return 'USUARIO'
    if accion == 'AUDITORIA_EXPORTADA':
        return 'AUDITORIA_EXPORTACION'
    return 'GENERAL'


def rol_actor_de(accion):
    modulo = modulo_de(accion)
    if modulo == 'COMANDAS':
        return 'MOZO'
    if modulo == 'CAJA':
        return 'CAJERO'
    return 'ADMIN'


def severidad_de(accion):
    if accion in SEVERIDAD_CRITICA:
        return AuditLog.Severidad.CRITICA
    if accion in SEVERIDAD_INFO:
        return AuditLog.Severidad.INFO
    return AuditLog.Severidad.ADVERTENCIA


def resultado_de(accion):
    if accion == 'ACCESO_DENEGADO':
        return AuditLog.EstadoResultado.DENEGADO
    if accion == 'LOGIN_FALLIDO_REITERADO':
        return AuditLog.EstadoResultado.FALLIDO
    return AuditLog.EstadoResultado.EXITOSO


def metodo_de(accion):
    if accion == 'ACCESO_DENEGADO' or accion == 'AUDITORIA_EXPORTADA':
        return 'GET'
    if 'SOFT_DELETE' in accion or accion == 'RECETA_INSUMO_ELIMINADO':
        return 'DELETE'
    if 'MODIFICAD' in accion:
        return 'PATCH'
    return 'POST'


def tabs_de(evento, modulo, severidad):
    """Replica matchesTab() del front-end para detectar eventos huerfanos."""
    tabs = []
    criticos_set = {
        'CAJA_DESCUADRE_DETECTADO', 'CAJA_CIERRE_FORZADO', 'CAJA_TURNO_REABIERTO',
        'INVENTARIO_AJUSTE_MANUAL_ELEVADO', 'INVENTARIO_MERMA_ELEVADA',
        'USUARIO_ESCALAMIENTO_PRIVILEGIOS', 'ACCESO_DENEGADO', 'LOGIN_FALLIDO_REITERADO',
    }
    if severidad == 'CRITICA' or 'ANULADO' in evento or 'ANULADA' in evento or evento in criticos_set:
        tabs.append('criticos')
    if modulo == 'COMANDAS' or evento.startswith('COMANDA_'):
        tabs.append('comandas')
    if modulo == 'CAJA' or evento.startswith('CAJA_') or evento.startswith('PAGO_'):
        tabs.append('caja')
    if modulo == 'INVENTARIO' or evento.startswith('INVENTARIO_'):
        tabs.append('inventario')
    if modulo == 'MENU' or evento.startswith('PLATO_') or evento.startswith('RECETA_'):
        tabs.append('menu')
    if (modulo == 'USUARIOS' or evento.startswith('USUARIO_')
            or evento.startswith('LOGIN_') or evento == 'ACCESO_DENEGADO'):
        tabs.append('usuarios')
    if evento.startswith('AUDITORIA_'):
        tabs.append('auditoria')
    return tabs


class Command(BaseCommand):
    help = 'Genera datos demo controlados para validar el panel de Auditoria de Riesgos.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset-demo',
            action='store_true',
            help='Elimina UNICAMENTE los registros demo (clave_alerta=DEMO_AUDITORIA) y termina.',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Permite ejecutar aunque DEBUG=False (solo para entornos controlados).',
        )

    # ------------------------------------------------------------------ #
    def handle(self, *args, **opts):
        if opts['reset_demo']:
            self._reset_demo()
            return

        if not settings.DEBUG and not opts['force']:
            raise CommandError(
                'Por seguridad este comando solo corre con DEBUG=True. '
                'Usa --force para forzarlo en un entorno controlado.'
            )

        if not Usuario.objects.exists():
            raise CommandError('No hay usuarios para asignar como responsables de los eventos demo.')

        eliminados = self._reset_demo(silent=True)
        if eliminados:
            self.stdout.write(f'Se eliminaron {eliminados} registros demo previos (idempotencia).')

        creados = self._seed()
        self._reporte(creados)

    # ------------------------------------------------------------------ #
    def _reset_demo(self, silent=False):
        total, _ = AuditLog.objects.filter(clave_alerta=DEMO_CLAVE).delete()
        if not silent:
            self.stdout.write(self.style.SUCCESS(
                f'Registros demo eliminados: {total}. No se toco ningun registro real.'
            ))
        return total

    def _user(self, rol):
        usuario = Usuario.objects.filter(rol__nombre=rol, is_active=True).first()
        if usuario:
            return usuario
        return (
            Usuario.objects.filter(rol__nombre='ADMIN').first()
            or Usuario.objects.first()
        )

    def _seed(self):
        admin = self._user('ADMIN')
        acciones = sorted(ACCIONES_AUDITABLES - ACCIONES_EXCLUIDAS)
        creados = []

        for idx, accion in enumerate(acciones):
            modulo = modulo_de(accion)
            entidad = entidad_de(accion)
            entidad_id = 1000 + idx
            severidad = severidad_de(accion)
            actor = self._user(rol_actor_de(accion))

            motivo = None
            if accion in ACCIONES_CON_MOTIVO_OBLIGATORIO:
                motivo = MOTIVOS.get(accion, f'Motivo demo requerido para {accion}.')

            contexto = {
                'ip': f'10.20.{idx % 6}.{(idx * 9) % 250 + 1}',
                'user_agent': USER_AGENTS[idx % len(USER_AGENTS)],
                'ruta': f'/admin-panel/api/demo/{modulo.lower()}/{entidad_id}/',
                'metodo_http': metodo_de(accion),
            }
            if accion in IMPACTOS:
                contexto['impacto_economico_estimado'] = Decimal(IMPACTOS[accion])

            descripcion = DEMO_PREFIX + DESCRIPCIONES.get(
                accion, accion.replace('_', ' ').capitalize() + '.'
            )

            log = AuditoriaService.registrar(
                usuario=actor,
                accion=accion,
                modulo=modulo,
                entidad=entidad,
                entidad_id=entidad_id,
                severidad=severidad,
                estado_resultado=resultado_de(accion),
                descripcion=descripcion,
                motivo=motivo,
                valores_anteriores={'estado': 'previo', 'ref': f'{entidad}#{entidad_id}'},
                valores_nuevos={'estado': 'posterior', 'evento': accion},
                datos_contextuales=contexto,
            )

            # Distribuye estados de revision y marca el registro como demo.
            estado_rev = REVISION_CICLO[idx % len(REVISION_CICLO)]
            log.estado_revision = estado_rev
            log.responsable_revision = (
                admin if estado_rev != AuditLog.EstadoRevision.PENDIENTE else None
            )
            log.clave_alerta = DEMO_CLAVE
            log.save(update_fields=[
                'estado_revision', 'responsable_revision', 'clave_alerta', 'updated_at',
            ])
            creados.append(log)

        return creados

    # ------------------------------------------------------------------ #
    def _reporte(self, creados):
        esperadas = ACCIONES_AUDITABLES - ACCIONES_EXCLUIDAS
        generadas = [log.codigo_evento for log in creados]
        generadas_set = set(generadas)

        faltantes = sorted(esperadas - generadas_set)
        duplicadas = sorted({a for a in generadas if generadas.count(a) > 1})

        por_modulo = self._contar(creados, lambda x: x.modulo)
        por_severidad = self._contar(creados, lambda x: x.severidad)
        por_revision = self._contar(creados, lambda x: x.estado_revision)

        huerfanos = []
        for log in creados:
            if not tabs_de(log.codigo_evento, log.modulo, log.severidad):
                huerfanos.append(log.codigo_evento)

        w = self.stdout.write
        w('')
        w(self.style.MIGRATE_HEADING('=== REPORTE seed_auditoria_demo ==='))
        w(f'Acciones esperadas (sin operativas excluidas): {len(esperadas)}')
        w(f'Acciones generadas: {len(generadas_set)} ({len(creados)} registros)')
        w(f'Acciones excluidas deliberadamente: {sorted(ACCIONES_EXCLUIDAS)}')

        if faltantes:
            w(self.style.ERROR(f'Acciones faltantes: {faltantes}'))
        else:
            w(self.style.SUCCESS('Acciones faltantes: ninguna'))

        if duplicadas:
            w(self.style.WARNING(f'Acciones duplicadas: {duplicadas}'))
        else:
            w('Acciones duplicadas: ninguna')

        w('')
        w('Total por modulo:')
        for k, v in sorted(por_modulo.items()):
            w(f'  {k:<12} {v}')
        w('Total por severidad:')
        for k, v in sorted(por_severidad.items()):
            w(f'  {k:<12} {v}')
        w('Total por estado de revision:')
        for k, v in sorted(por_revision.items()):
            w(f'  {k:<14} {v}')

        if 'MESAS' in por_modulo:
            w(self.style.ERROR('ADVERTENCIA: se genero el modulo MESAS (no permitido).'))
        else:
            w(self.style.SUCCESS('OK: no se genero ningun registro del modulo MESAS.'))

        if huerfanos:
            w(self.style.WARNING(
                f'ADVERTENCIA: eventos que no caen en ninguna pestaña del front: {huerfanos}'
            ))
        else:
            w(self.style.SUCCESS('OK: todos los eventos caen en al menos una pestaña del front.'))

        w('')
        w(self.style.MIGRATE_HEADING('Como usar / limpiar:'))
        w('  Generar:  python manage.py seed_auditoria_demo')
        w('  Limpiar:  python manage.py seed_auditoria_demo --reset-demo')
        w(f'  Marca de limpieza: clave_alerta = "{DEMO_CLAVE}" / descripcion con prefijo "{DEMO_PREFIX.strip()}"')
        w('')

    @staticmethod
    def _contar(creados, key):
        conteo = {}
        for log in creados:
            k = key(log)
            conteo[k] = conteo.get(k, 0) + 1
        return conteo
