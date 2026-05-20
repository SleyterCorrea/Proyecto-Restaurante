# Tasks: Dashboard Premium Redesign

## Phase 1: Backend Foundation

- [x] 1.1 Update `api_ventas_turno` in `apps/reportes/views.py` to calculate trends vs previous shift.
- [x] 1.2 Implement `api_ventas_historial` in `apps/reportes/views.py` with search/filter on comanda/mesa.
- [x] 1.3 Add URL pattern for `api_ventas_historial` in `apps/reportes/urls.py`.

## Phase 2: UI Styling (Glassmorphism 2.0)

- [x] 2.1 Add refined glassmorphism styles and color tokens to `<style>` in `templates/admin_panel/reportes.html`.
- [x] 2.2 Define utility classes for trend indicators (success/danger/neutral) in `reportes.html`.

## Phase 3: Layout Overhaul

- [x] 3.1 Redesign KPI cards with trend badges in `templates/admin_panel/reportes.html`.
- [x] 3.2 Implement horizontal progress bars for "Top Selling" section in `reportes.html`.
- [x] 3.3 Create the Sales History Table component with Search input in `reportes.html`.

## Phase 4: Alpine.js Wiring

- [x] 4.1 Update `reportesApp()` state to include `ventasHistorial`, `searchQuery`, and trend data.
- [x] 4.2 Implement `cargarVentasHistorial()` method in Alpine.js.
- [x] 4.3 Add `watch` on `searchQuery` to trigger debounced API calls.

## Phase 5: Verification

- [x] 5.1 Verify KPI trend calculation logic with unit tests.
- [x] 5.2 Test search functionality in the History Table (Manual/Integration).
- [x] 5.3 Confirm layout responsiveness on different screen sizes.
