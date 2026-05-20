# Design: Complete Restaurant System

## Architecture Overview
- **Backend**: Django 4.2 with DRF (Django REST Framework).
- **Frontend**: Django Templates + Alpine.js for real-time reactivity.
- **Database**: PostgreSQL 15 (Dockerized).
- **Auth**: JWT via `simplejwt`.

## Database Schema Mapping (Django -> SQL)
- `apps.usuarios`:
  - `Rol` -> `rol` table.
  - `Usuario` (Custom) -> `usuario` table.
- `apps.mesas`:
  - `Zona` -> `zona` table.
  - `Mesa` (Update) -> `mesa` table (relates to `Zona`).
- `apps.menu`:
  - `Categoria` -> `categoria_plato` table.
  - `Plato` -> `plato` table.
- `apps.comandas`:
  - `Comanda` -> `comanda` table (adds `codigo_comanda`).
  - `LineaComanda` -> `linea_comanda` table (adds tracking timestamps).
  - `ComandaHistorialEstado` -> `comanda_historial_estado` table.
- `apps.inventario`:
  - `UnidadMedida`, `Insumo`, `RecetaInsumo`, `MovimientoInventario`.
- `apps.caja`:
  - `CajaTurno`, `MetodoPago`, `Pago`.

## Business Logic Patterns
- **Atomic Operations**: Using `django.db.transaction.atomic` for order creation and payment processing.
- **Signals**: `post_save` on `Insumo` to trigger plate availability updates.
- **Polling**: Polling logic updated to include `last_updated` timestamps to optimize data transfer.

## Security Design
- **JWT Middleware**: Standard DRF JWT authentication.
- **Custom Permissions**:
  - `IsMozo`, `IsCocinero`, `IsCajero`, `IsAdmin`.
- **CORS/CSRF**: Configured for secure API interaction.

## UI Design System
- **Theme**: Consistent Dark Mode using the existing color palette.
- **Charts**: Integration of `Chart.js` via CDN.
- **Reactivity**: Alpine.js for KDS timers and Cashier change calculation.
