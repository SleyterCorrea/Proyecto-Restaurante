"""Domain exceptions shared by the restaurant modules."""


class AppError(Exception):
    """Base exception for expected application errors."""

    status_code = 400
    code = "app_error"

    def as_dict(self):
        return {"error": str(self), "code": self.code}


class ReglaNegocioViolada(AppError):
    code = "regla_negocio_violada"


class RecursoNoEncontrado(AppError):
    status_code = 404
    code = "recurso_no_encontrado"


class AccesoNoAutorizado(AppError):
    status_code = 403
    code = "acceso_no_autorizado"


class DatosInvalidos(AppError):
    code = "datos_invalidos"


class MesaConComandaActiva(ReglaNegocioViolada):
    status_code = 409
    code = "mesa_con_comanda_activa"


class StockInsuficiente(ReglaNegocioViolada):
    code = "stock_insuficiente"

    def __init__(self, insumo, disponible=None, requerido=None, insumo_id=None):
        self.insumo = insumo
        self.insumo_id = insumo_id
        self.disponible = disponible
        self.requerido = requerido
        super().__init__(f'Stock insuficiente para "{insumo}".')

    def as_dict(self):
        data = super().as_dict()
        data.update({
            "insumo": self.insumo,
            "stock_disponible": float(self.disponible) if self.disponible is not None else None,
            "stock_requerido": float(self.requerido) if self.requerido is not None else None,
            "insumo_id": self.insumo_id,
        })
        return data


class CajaNoAbierta(ReglaNegocioViolada):
    code = "caja_no_abierta"


class TransicionEstadoInvalida(ReglaNegocioViolada):
    code = "transicion_estado_invalida"


class PagoInvalido(ReglaNegocioViolada):
    code = "pago_invalido"


class OperacionNoPermitida(ReglaNegocioViolada):
    code = "operacion_no_permitida"
