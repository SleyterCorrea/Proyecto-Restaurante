# Proposal: Funcionalidad de unir mesas (máximo 3)

## Intent
Permitir que un mozo asocie una sola comanda a múltiples mesas físicas (hasta 3), facilitando la atención de grupos grandes sin duplicar pedidos y consolidando el cobro en una sola transacción.

## Scope

### In Scope
- Extensión del modelo `Comanda` con campo `mesas_adicionales` (M2M).
- Actualización de `api_crear_comanda` para aceptar una lista de `mesa_ids`.
- Lógica atómica para marcar todas las mesas del grupo como `OCUPADA`.
- Actualización de `api_liberar_mesa` para liberar todas las mesas asociadas.
- UI en Pantalla 1 (`toma_pedidos.html`) con selector multimesa y límite de 3.

### Out of Scope
- División de cuentas (Split bill).
- Reservas de grupos de mesas.

## Capabilities

### New Capabilities
- `union-mesas`: Lógica de validación y gestión de grupos de mesas vinculadas a una sola orden.

### Modified Capabilities
- `comandas`: Se modifica el requerimiento de asociación 1:1 a 1:N (N <= 3).
- `mesas`: Se modifica la lógica de liberación para que sea dependiente de la unión.

## Approach
Se implementará la **Opción 2** de la exploración: mantener `mesa` como FK principal (para reportes existentes) y añadir `mesas_adicionales` (M2M) para las extras. Se usará `transaction.atomic` para asegurar que el estado de todas las mesas cambie en conjunto. La UI se actualizará en Alpine.js para gestionar un array de IDs.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `apps/comandas/models.py` | Modified | Agregar `mesas_adicionales` y método `get_todas_las_mesas()`. |
| `apps/comandas/views.py` | Modified | Actualizar `api_crear_comanda` y `api_liberar_mesa`. |
| `apps/mesas/views.py` | Modified | Actualizar `api_estado_actual` para reflejar uniones en el polling. |
| `templates/mesero/toma_pedidos.html` | Modified | Selector multimesa en Alpine.js. |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Colisión de selección | Low | Uso de `transaction.atomic` y validación de estado `LIBRE` antes de crear. |
| Mesas "huérfanas" | Medium | Lógica de limpieza en `api_liberar_mesa` que itera sobre el M2M. |

## Rollback Plan
Eliminar el campo `mesas_adicionales` mediante migración de Django y revertir cambios en vistas/templates. El sistema volverá a ignorar uniones.

## Success Criteria
- [ ] Selección de hasta 3 mesas en la UI.
- [ ] Ocupación simultánea de todas las mesas en el plano.
- [ ] Liberación simultánea de todas las mesas al cerrar comanda.
