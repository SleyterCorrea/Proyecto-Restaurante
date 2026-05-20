# Design: Funcionalidad de unir mesas (máximo 3)

## Technical Approach
Extensión del modelo `Comanda` para soportar una relación 1:N (una orden, múltiples mesas) mediante un campo `ManyToManyField` complementario. Se actualiza el flujo de creación y liberación para gestionar el estado de todas las mesas de forma atómica.

## Architecture Decisions

### Decision: Relación Principal + Satélites
**Choice**: Mantener `mesa` (ForeignKey) y añadir `mesas_adicionales` (ManyToManyField).
**Alternatives considered**: Migrar todo a M2M.
**Rationale**: Mantener la FK principal evita romper reportes de ventas, lógica de filtros por zona y otras vistas que ya dependen de `comanda.mesa`. Las mesas adicionales actúan como satélites que comparten la misma orden.

### Decision: Validación en Servidor vs Cliente
**Choice**: Validación duplicada (Frontend para feedback inmediato, Backend para integridad).
**Rationale**: Evita race conditions donde dos mozos intentan unir la misma mesa simultáneamente desde clientes distintos.

## Data Flow
UI (Mesas Seleccionadas: [ID1, ID2]) ──→ API (POST /crear/) ──→ DB (Atomic Transaction)
                                                                 │
                                                                 ├── Create Comanda (Mesa: ID1)
                                                                 ├── Add ID2 to mesas_adicionales
                                                                 └── Set ID1, ID2 as OCUPADA

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `apps/comandas/models.py` | Modify | Agregar `mesas_adicionales` y property `get_todas_las_mesas`. |
| `apps/comandas/views.py` | Modify | Actualizar `api_crear_comanda` (soporte `mesa_ids`) y `api_liberar_mesa` (limpieza total). |
| `apps/mesas/views.py` | Modify | Actualizar `api_estado_actual` para mapear comandas a mesas satélites. |
| `templates/mesero/toma_pedidos.html` | Modify | Refactor de `pedidoApp` en Alpine.js para gestionar array de selección. |

## Interfaces / Contracts

```python
# apps/comandas/models.py
class Comanda(models.Model):
    mesa = models.ForeignKey(Mesa, ...) # Principal
    mesas_adicionales = models.ManyToManyField(Mesa, related_name='uniones_adicionales', blank=True)
    
    @property
    def todas_las_mesas(self):
        # Implementación conceptual
        return [self.mesa] + list(self.mesas_adicionales.all())
```

## Testing Strategy
- **Unit**: Testear el método `todas_las_mesas`.
- **Integration**: Validar que `api_crear_comanda` con 2 mesas marque ambas como `OCUPADA`.
- **E2E**: Verificar que en la UI, seleccionar 3 mesas y luego una 4ta dispare la alerta.

## Migration / Rollout
Se requiere una migración de Django para añadir el campo M2M. No se requiere migración de datos (las comandas existentes simplemente tendrán `mesas_adicionales` vacío).
