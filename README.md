# vik-isit

Ministry performance analysis platform. Tracks 10 Indian ministries against 3
headline KPIs each (FY2014-15 → present), scores each on a transparent,
weighted 0–100 framework (see [`app/scoring.py`](app/scoring.py)), and layers
on Claude-generated insights plus the Tarka analytical chatbot.

**Data status:** all 30 KPIs across the 10 ministries run on a curated,
provenance-tracked layer of official data — Tier-A (Finance, Petroleum,
Agriculture, Railways, Power) under [`data/tier_a/`](data/tier_a/README.md), and
Tier-B (Commerce & Industry, Defence, Education, Skill Development & Labour, Road
Transport & Highways) under [`data/tier_b/`](data/tier_b/README.md). See
[`docs/DATA_PIPELINE.md`](docs/DATA_PIPELINE.md). Every figure carries a revision
status; where no official series exists the number is an assembled estimate,
flagged `Estimated` and labelled a proxy in the UI.

## Run it

### Backend (FastAPI, port 8000)

```bash
python -m venv venv && venv/Scripts/pip install -r requirements.txt   # first time
cp .env.example .env            # add ANTHROPIC_API_KEY for insights/Tarka (optional)

python -m app.seed_dashboard    # ministries + KPI rows
python -m app.tier_a_pipeline   # compute the 15 Tier-A KPIs from data/tier_a/
python -m app.tier_b_pipeline   # compute the 15 Tier-B KPIs from data/tier_b/
python main.py                  # serve on http://localhost:8000
```

### Frontend (Vite + React, port 5173)

```bash
cd frontend && npm install && npm run dev
```

## Keeping the data current

```bash
python -m app.check_sources     # which of all 30 KPIs are behind the latest official release?
# ...edit data/tier_a/*.csv or data/tier_b/*.csv from the cited source...
python -m app.tier_a_pipeline    # recompute Tier-A
python -m app.tier_b_pipeline    # recompute Tier-B  (both also run on "Sync Live Data" / POST /sync)
```

A [scheduled GitHub Actions workflow](.github/workflows/check-data-freshness.yml)
runs `check_sources` weekly and opens an issue when something needs attention —
nothing here auto-writes a KPI value; see [`data/tier_a/README.md`](data/tier_a/README.md#automation---whats-real-vs-best-effort)
for why. Full workflow, revision codes and per-KPI sources:
[`docs/DATA_PIPELINE.md`](docs/DATA_PIPELINE.md) and [`data/tier_a/README.md`](data/tier_a/README.md).

## Deploying

Frontend on Vercel, backend + Postgres on Render, both free-tier. See
[`DEPLOYMENT.md`](DEPLOYMENT.md).

## Tests

```bash
venv/Scripts/python -m pytest -q
```

## Key modules

| path | role |
|---|---|
| `app/connectors/tier_a/` · `tier_b/` | the 10 ministry connectors + KPI specs |
| `app/connectors/provenance.py` | curated-data loader (`data/tier_a/`, `data/tier_b/`) |
| `app/tier_a_pipeline.py` · `tier_b_pipeline.py` | recompute → DB (series, current value, audited history, GAPS.md) |
| `app/check_sources.py` | freshness report + best-effort auto-fetchers |
| `app/pipeline/sync_service.py` | `POST /sync` — routes tier_a sources to the pipeline |
| `app/kpi_specifications.py` / `app/analysis_frameworks.py` | KPI definitions + the analyst rubric |
| `frontend/src/components/charts/` | chart rendering (Recharts) |
| `frontend/src/components/KpiProvenance.jsx` | per-KPI source / quality / caveats panel |
