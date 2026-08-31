# Ministry Performance Dashboard - Frontend

React + Vite dashboard for the Ministry Performance API.

## Stack

- React 18 + Vite
- Tailwind CSS
- Recharts (charts)
- Axios (HTTP)
- TanStack React Query (server state, caching, loading/error states)

## Setup

Requires Node.js 18+ (not installed in the environment this was scaffolded in - install it first: https://nodejs.org).

```bash
cd frontend
npm install
npm run dev
```

The app runs at `http://localhost:5173` and expects the API at `http://localhost:8000` (see `.env`, `VITE_API_BASE_URL`).

The backend (`app/main.py`) now has CORS enabled for `http://localhost:5173` - restart the backend after pulling this change.

## Structure

- `src/api/` - axios client + endpoint functions
- `src/hooks/` - React Query hooks wrapping each endpoint
- `src/components/` - UI: `Header`/`SyncButton`, `MinistryGrid`/`MinistryCard`, KPI stats and charts, `InsightsPanel`, `ErrorBoundary`/`ErrorBanner`, loading skeletons
- Each `MinistryCard` is wrapped in its own `ErrorBoundary` so one bad card can't take down the whole grid; a top-level boundary covers the rest of the app.

## Notes

- `/ministries` returns the ministry list only; each card fetches `/ministries/{id}` for its KPIs.
- Insights (`POST /ministries/{id}/insights`) are cached server-side per KPI snapshot, so they're fetched once per card and reused until KPI values change (e.g. after a sync).
- The trend chart uses the first displayed KPI's `/kpis/{id}/history`; ministries with fewer than 2 history points show a placeholder instead of an empty chart.
- "Sync Data" calls `POST /sync` and invalidates all cached ministry/KPI/insight queries on success, so cards refetch automatically.
