# Proposal: Implement Nuevo Insumo and Editar Insumo functionality

## Intent

The inventory management system currently lacks the ability to create or edit supplies (insumos) through the administrative dashboard. The existing "Nuevo Insumo" button only shows an alert, preventing users from adding new stock items to the system.

## Scope

### In Scope
- API endpoint for `UnidadMedida`.
- "Nuevo Insumo" modal in the dashboard.
- "Editar Insumo" modal in the dashboard.
- Alpine.js logic to handle creation and edition.
- Success notifications and list refreshing.

### Out of Scope
- Bulk upload of insumos.
- Supply deletion UI (outside the active field toggle).

## Capabilities

### New Capabilities
- `unidad-medida-api`: API to fetch units of measure.

### Modified Capabilities
- `gestion-inventario`: Add UI support for creation and edition of supplies.

## Approach

Modal-based implementation using Bootstrap 5 and Alpine.js.
1.  **Backend**: Add `UnidadMedidaViewSet` to `apps/inventario/views.py` and register in `urls.py`.
2.  **Frontend**:
    - Add `modalInsumo` to `templates/admin_panel/inventario.html`.
    - Update `inventarioApp` to manage form state and fetch units.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `apps/inventario/views.py` | Modified | Add `UnidadMedidaViewSet`. |
| `apps/inventario/urls.py` | Modified | Register `UnidadMedidaViewSet`. |
| `templates/admin_panel/inventario.html` | Modified | Add modal and JS implementation. |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Validation Errors | Low | Use `InsumoSerializer` for robust backend validation. |

## Rollback Plan

Revert modified files to their previous git state.

## Success Criteria

- [ ] "Nuevo Insumo" modal opens and saves successfully.
- [ ] "Editar Insumo" modal opens with populated data and saves successfully.
- [ ] Supply list refreshes automatically after saving.
