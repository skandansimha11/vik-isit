# Tier-A / Tier-B data pipeline

How all 30 KPIs across the 10 ministries get their numbers, and how to keep them
current. **Tier-A** = Finance, Petroleum, Agriculture, Railways, Power
(`data/tier_a/`, `app/tier_a_pipeline.py`). **Tier-B** = Commerce & Industry,
Defence, Education, Skill Development & Labour, Road Transport & Highways
(`data/tier_b/`, `app/tier_b_pipeline.py`). The two are structurally identical -
Tier-B reuses every connector base class, helper and pipeline behaviour from
Tier-A; only the curated-data root differs. Everything below describes Tier-A;
substitute `tier_b` throughout for the other five ministries.

## Architecture

```
data/tier_a/*.csv                     curated official figures + provenance (source of truth)
  └─ app/connectors/provenance.py     ProvenanceDataset - load, type-coerce, de-dup
       └─ app/connectors/tier_a/*.py  one connector per ministry: formula + validation + series
            ├─ app/tier_a_pipeline.py  refresh_tier_a() -> writes KPISeriesPoint / KPI / KPISource / KPIHistory
            ├─ app/pipeline/sync_service.py  POST /sync routes "tier_a"/"tier_b" sources here
            └─ app/check_sources.py    freshness report + best-effort auto-fetchers
```

`app/connectors/tier_b/` mirrors this exactly for the other five ministries, off
`data/tier_b/`. `app/seed_dashboard.py` now only creates the KPI rows - all 30
KPIs' presentation + series are owned by the two pipelines (no synthetic data).

## First-time / rebuild

```bash
python -m app.seed_dashboard      # 10 ministries + 30 KPI rows
python -m app.tier_a_pipeline     # compute the 15 Tier-A KPIs from data/tier_a/
python -m app.tier_b_pipeline     # compute the 15 Tier-B KPIs from data/tier_b/
```

Order matters: `seed_dashboard` creates the KPI rows; the pipelines own the
presentation + series and never write synthetic data.

## Routine refresh (a few times a year)

```bash
python -m app.check_sources                 # what's behind? is the source reachable?
# ...edit the relevant data/tier_a/*.csv from the cited document...
python -m app.tier_a_pipeline               # recompute; appends audited history where values moved
```

`python -m app.check_sources --fetch` additionally runs best-effort auto-fetchers
for the few sources that allow it (PPAC, MoSPI CPI, PIB rail freight). They never
overwrite `Actual`/`Revised` rows and degrade to a "update manually" message on
any failure - the curated CSVs stay authoritative.

### Suggested cadence by source

| source | typical new release | check |
|---|---|---|
| Union Budget / Economic Survey | Jan–Feb | Feb |
| PPAC Ready Reckoner / Snapshot | monthly | quarterly |
| MoSPI CPI | monthly (~12th) | quarterly |
| Indian Railways / PIB freight | monthly | quarterly |
| PFC Report on Performance of Power Utilities | annual (~mid-year) | Aug |
| CEA Power Supply Position | monthly | quarterly |

Consider a scheduled weekly `python -m app.check_sources` (see `/schedule`).
`check_sources` currently tracks **Tier-A** freshness only; refresh Tier-B by
editing `data/tier_b/*.csv` from the cited source and re-running
`python -m app.tier_b_pipeline`.

### Tier-B data notes

Several Tier-B KPIs have **no single official published series** - industrial
import dependence, PLI domestic value-addition, defence equipment vintage,
exam-integrity incident counts, pre-FY2021-22 logistics cost. Those are assembled
from the cited documents, flagged `Estimated`, listed in `data/tier_b/GAPS.md`,
and shown with a `LOW` quality badge + `Proxy metric` tag in the UI. The 15
Tier-B specs live in `app/connectors/tier_b/spec.py`.

## KPI framing & targets

Each Tier-A KPI carries, in `app/connectors/tier_a/spec.py`:

* `display_title` - the layman heading shown on the card (e.g. "Government Budget
  Gap"); the technical `name` becomes a grey subtitle.
* `plain_note` - one sentence explaining what the metric means.
* `target` - `TierAkpiTarget(official, aspirational, official_label, aspirational_label)`.
  The chart draws the official line (grey dashed), the aspirational line (green
  dotted) and a faint band between them; the card prints "Target X → aspiration Y".
* Charts are single-series by design - secondary metrics go to the data table.

To change a target or heading, edit `spec.py` and re-run `python -m app.tier_a_pipeline`.

## Provenance surfaced in the product

* Each KPI card shows a data-quality badge, a PROXY tag where relevant, the
  source (linked), the latest period, its revision, and "as published <month>".
* `GET /kpis/{id}/provenance` returns the definition, formula, caveats, the
  per-period audit trail (formula + inputs + source doc + page ref), the list of
  unresolved data points, and the backing data files.
* `data/tier_a/GAPS.md` is regenerated on every pipeline run and lists every
  figure still pending confirmation against its primary document.

## Adding a KPI / changing a formula

1. Add/adjust the CSV under `data/tier_a/` (keep the provenance columns).
2. Add the `TierAKpi` entry in `app/connectors/tier_a/spec.py`.
3. Add a `_compute_<key>` method on the ministry connector; reuse the helper
   calculators (`calculate_*`, `deflate_income`, …).
4. `python -m app.tier_a_pipeline --kpi <key> --dry-run` to check, then without
   `--dry-run`.
5. Add a case to `tests/test_tier_a_pipeline.py`.
