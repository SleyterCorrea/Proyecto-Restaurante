# Design: Dashboard Premium Redesign

## Technical Approach

Redesign the administrative reports dashboard to match the premium "Analytics Overview" reference. This involves updating the UI to a more refined glassmorphism style (Glassmorphism 2.0), adding trend indicators to KPIs, changing the top-selling visualization to horizontal bars, and implementing a searchable, detailed sales history table.

## Architecture Decisions

### Decision: KPI Trend Calculation
**Choice**: Calculate trends in the backend view by comparing current shift metrics against the previous closed shift of the same caja.
**Alternatives considered**: Comparing against yesterday's total or calculating trends in the frontend.
**Rationale**: Real-time comparison against the previous shift is more relevant for a restaurant's operational flow than a calendar-day comparison. Doing it in the backend keeps the frontend logic lean.

### Decision: Detailed Sales History Search
**Choice**: Server-side filtering using Django's `icontains` on `codigo_comanda` and related `mesa` number.
**Alternatives considered**: Client-side filtering.
**Rationale**: Better performance as the sales history grows.

### Decision: Product Detail Concatenation
**Choice**: Use Python processing in the view to concatenate dish names and quantities (e.g., "2x Ceviche, 1x Pisco Sour").
**Alternatives considered**: Using Postgres `StringAgg`.
**Rationale**: More portable and easier to format for different DB backends (SQLite/Postgres).

## Data Flow

    Dashboard UI (Alpine.js) <───> API Endpoints (Django/DRF) <───> Database (PostgreSQL/SQLite)
          │                                 │
          └─ Fetch KPIs + Trends ───────────┤
          ├─ Fetch Top Selling ─────────────┤
          └─ Fetch Sales Historial (Search) ┘

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `apps/reportes/views.py` | Modify | Update KPI logic for trends; add `api_ventas_historial` endpoint. |
| `apps/reportes/urls.py` | Modify | Register `api_ventas_historial`. |
| `templates/admin_panel/reportes.html` | Modify | Full UI overhaul to match reference; add table logic; update Alpine state. |

## Interfaces / Contracts

### GET `/admin-panel/reportes/api/ventas-historial/?search=...`
```json
{
  "results": [
    {
      "id": 123,
      "codigo": "COM-001",
      "fecha": "2023-10-24 15:30",
      "mesa": "5",
      "detalle": "2x Lomo Saltado, 1x Inka Kola",
      "bruto": 85.00,
      "impuesto": 8.50,
      "neto": 76.50,
      "metodo": "Efectivo",
      "estado": "PAGADO"
    }
  ]
}
```

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit | Trend calculation | Test view logic with mock shifts. |
| Integration | History API search | Assert search query returns correct records. |
| Manual | UI Responsive | Verify glassmorphism layout on mobile/desktop. |

## Migration / Rollout

No migration required. This is a pure UI and API extension.
