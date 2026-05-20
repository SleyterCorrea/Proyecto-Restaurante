# Proposal: Dashboard Detailed Sales

## Intent

Add a detailed sales table to the reports dashboard to provide the user with specific knowledge of what was sold, at what price, and in what quantities, improving operational oversight.

## Scope

### In Scope
- New API endpoint `api_ventas_detalladas` in `apps.reportes`.
- Detailed sales table in `templates/admin_panel/reportes.html`.
- Alpine.js integration to fetch and render the sales list.
- Support for "Detalle" column (Dish names x Quantity).

### Out of Scope
- Detailed filtering (by date/waiter) — deferred for a later feature.
- PDF generation of the detailed list (CSV already exists).

## Capabilities

### New Capabilities
- `detailed-sales-tracking`: Ability to view individual transaction details including line items and payment methods in the dashboard.

### Modified Capabilities
- None

## Approach

- **Backend**: Create `api_ventas_detalladas` in `apps/reportes/views.py`. It will filter `Pago` objects for the active `CajaTurno`, prefetching `comanda__lineas__plato`.
- **Frontend**: Insert a new `.glass-card` containing a Bootstrap table below the charts in `reportes.html`. 
- **JS**: Add `ventasDetalladas: []` to the Alpine.js state and a `cargarVentasDetalladas()` method.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `apps/reportes/views.py` | Modified | Add `api_ventas_detalladas` view. |
| `apps/reportes/urls.py` | Modified | Add URL pattern for the new endpoint. |
| `templates/admin_panel/reportes.html` | Modified | Add table UI and Alpine.js logic. |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Performance with many sales | Low | Filter by active shift only; prefetch related objects. |
| UI Clutter | Med | Use a responsive table with a max-height/scroll or pagination. |

## Rollback Plan

- Revert changes to `reportes.html`, `views.py`, and `urls.py`.

## Success Criteria

- [ ] Admin can see a table with at least 5 columns: Código, Mesa, Detalle, Total, Hora, Método.
- [ ] Table updates automatically when the dashboard is loaded.
- [ ] UI maintains the dark glassmorphism aesthetic.
