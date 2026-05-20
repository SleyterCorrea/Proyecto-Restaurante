# Exploration: Complete Restaurant System

## Summary
The goal is to expand the existing RestaurantOS project into a full-featured management system, migrating to PostgreSQL and implementing 7 critical phases: Migration, Users/JWT, Inventory, KDS, Cashier, Reports, and Infrastructure (Docker/Tests).

## Codebase Analysis
- **Current State**: 
  - Django 4.2 with 3 apps (`menu`, `mesas`, `comandas`).
  - Simple models (no zones, no complex inventory, no roles).
  - High-quality frontend with Alpine.js and dark mode.
- **New Requirements**:
  - Deep database schema update following a provided SQL script.
  - New apps: `usuarios`, `inventario`, `caja`, `reportes`.
  - Advanced business logic: stock validation, atomic payments, real-time KDS alerts.

## Technical Considerations
- **DB Migration**: Moving from SQLite to PostgreSQL 15. Models must be carefully updated to match SQL constraints (identity columns, foreign keys, unique constraints).
- **JWT Auth**: Replacing simple login with `djangorestframework-simplejwt`. Custom User model required.
- **KDS Polling**: Extending current polling logic to include preparation time alerts and role-based actions.
- **Inventory Control**: Post-save signals for stock alerts and atomic deduction during payment.

## Risk Assessment
- **Migration**: Data loss during the transition from SQLite floors (string) to SQL zones (foreign key).
- **Complexity**: Multiple interdependent modules (Cashier depends on Comandas, which depends on Inventory).
- **Performance**: N+1 queries in Comandas/KDS (already identified in previous review).
