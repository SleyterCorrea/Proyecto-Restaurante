# Proposal: Complete Restaurant System

## Goal
Transform RestaurantOS into a professional, scalable, and audit-ready management system by implementing a complex SQL schema, JWT security, KDS, inventory control, and automated testing.

## Proposed Changes

### Phase 1: PostgreSQL & Model Migration
- Setup Docker with PostgreSQL 15.
- Map SQL schema to Django models in existing and new apps.
- Implement data migration from current models to the new schema.

### Phase 2: User System & JWT (4 Roles)
- Create `apps.usuarios` with custom `Usuario` and `Rol` models.
- Integrate `simplejwt` for authentication.
- Define permissions for Mozo, Cocinero, Cajero, and Admin.

### Phase 3: Inventory & Recipes
- Create `apps.inventario`.
- Implement `Insumo`, `RecetaInsumo`, and `MovimientoInventario`.
- Add Django Signals to auto-disable plates when stock reaches 0.

### Phase 4: KDS (Kitchen Display System)
- New template `templates/cocina/kds.html`.
- Real-time preparation time alerts with Alpine.js.
- Role-based actions (Cocinero only).

### Phase 5: Cashier Module
- Opening/Closing of Cash Shift (`CajaTurno`).
- Atomic payment logic with stock deduction and table release.
- Support for multiple payment methods.

### Phase 6: Reports & Dashboard
- Implementation of KPIs: Total sales, top plates, sales by hour.
- Visual charts using Chart.js.
- CSV Export functionality.

### Phase 7: Infrastructure, Docs & Testing
- Dockerization (Dockerfile + docker-compose).
- Pytest suite with 60% coverage.
- Swagger documentation (drf-spectacular).

## Rollback Plan
- Maintain the SQLite version as a backup.
- Incremental migrations per app to allow partial rollbacks.
