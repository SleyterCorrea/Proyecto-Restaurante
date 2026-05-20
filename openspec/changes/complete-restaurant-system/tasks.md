# Tasks: Complete Restaurant System

## Phase 1: Infrastructure & Model Migration
- [ ] 1.1 Configure Dockerfile and docker-compose.yml (Django + Postgres 15).
- [ ] 1.2 Update `settings.py` for PostgreSQL and installed apps.
- [ ] 1.3 Implement `apps.usuarios` with custom User and Role models.
- [ ] 1.4 Implement `apps.inventario` (Unit, Insumo, Recipe).
- [ ] 1.5 Implement `apps.caja` (Shift, Payment Method, Payment).
- [ ] 1.6 Update `apps.mesas`, `apps.menu`, and `apps.comandas` models to match SQL schema.
- [ ] 1.7 Create and run initial migrations.
- [ ] 1.8 Create a migration script to import data from SQLite to Postgres.

## Phase 2: Security & JWT
- [ ] 2.1 Install and configure `djangorestframework-simplejwt`.
- [ ] 2.2 Create Auth endpoints (Login, Refresh, Logout).
- [ ] 2.3 Implement custom permission classes for each role.
- [ ] 2.4 Update `templates/registration/login.html` with the system aesthetic.

## Phase 3: Inventory Logic
- [ ] 3.1 Implement stock validation during order creation/update.
- [ ] 3.2 Create Django Signal to disable plates when an ingredient stock hits 0.
- [ ] 3.3 Create API for inventory manual adjustments.

## Phase 4: KDS Module
- [ ] 4.1 Implement `templates/cocina/kds.html` and its view.
- [ ] 4.2 Add Alpine.js logic for real-time preparation timers.
- [ ] 4.3 Add preparation time alerts (pulsing red border).
- [ ] 4.4 Implement role-based state updates (Cocinero only).

## Phase 5: Cashier & Payments
- [ ] 5.1 Implement `templates/caja/apertura.html`, `cobrar.html`, and `cierre.html`.
- [ ] 5.2 Implement atomic payment logic (COBRADA, deduct stock, move inv, release mesa).
- [ ] 5.3 Add real-time change calculation in the payment view.

## Phase 6: Analytics & Reports
- [ ] 6.1 Implement KPI endpoints (Sales, Top Plates, Hourly Sales).
- [ ] 6.2 Integrate Chart.js in `templates/admin/reportes.html`.
- [ ] 6.3 Implement CSV export functionality.

## Phase 7: Testing & Documentation
- [ ] 7.1 Setup Pytest and `pytest-cov`.
- [ ] 7.2 Implement the 7 critical test cases mentioned in the prompt.
- [ ] 7.3 Configure `drf-spectacular` for Swagger docs at `/api/docs/`.
- [ ] 7.4 Update `README.md` with full installation and usage guide.
