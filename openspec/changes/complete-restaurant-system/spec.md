# Specifications: Complete Restaurant System

## 1. Authentication & Roles
- **Login**: MUST return access and refresh JWT tokens.
- **Roles**:
  - `MOZO`: Can see tables, create orders, and track their own history.
  - `COCINERO`: EXCLUSIVE access to KDS to mark items as "Ready".
  - `CAJERO`: Can process payments for "Ready" orders and manage cash shifts.
  - `ADMIN`: Full access to all modules, including reports and inventory.

## 2. Inventory Logic
- **Stock Validation**: Every time an item is added to an order, the system MUST verify available stock for all recipe ingredients.
- **Auto-Disable**: If an ingredient stock reaches 0, all associated plates MUST be marked as `disponible=False` via signals.
- **Stock Deduction**: MUST happen atomically during the payment process.

## 3. KDS (Kitchen Display System)
- **View**: A grid of cards showing active orders for the kitchen.
- **Alerts**: A card MUST pulse or show a red border if the preparation time exceeds the plate's `tiempo_preparacion_min`.
- **States**: Items transition from PENDIENTE -> EN_PREP -> LISTO.

## 4. Cashier & Payments
- **Flow**: A cashier MUST open a shift with an initial amount before processing payments.
- **Payment**: Supports Cash, Card, and Digital wallets. Calculates change in real-time.
- **Atomic Release**: Payment MUST:
  1. Mark comanda as COBRADA.
  2. Deduct stock.
  3. Register inventory movement.
  4. Release the table to LIBRE.

## 5. Reports
- **Sales KPI**: MUST show total sales of the current shift and day.
- **Top Plates**: Top 5 most ordered plates via bar chart.
- **Export**: Admin MUST be able to download a CSV of the day's orders.
