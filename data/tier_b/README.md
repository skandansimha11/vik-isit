# `data/tier_b/` — curated data layer for the 15 Tier-B KPIs

Every KPI for **Commerce & Industry, Defence, Education, Skill Development &
Labour, and Road Transport & Highways** is computed from the CSV files here.
Same contract as [`data/tier_a/`](../tier_a/README.md): nothing is scraped at
runtime, these files *are* the source of truth, and the connectors in
`app/connectors/tier_b/` apply the documented formula, validate, and build the
dashboard series from them.

## File layout

| file | KPI it feeds |
|---|---|
| `commerce/import_dependence.csv` | Reliance on Imported Industrial Goods (proxy) |
| `commerce/manufacturing.csv` | Manufacturing's Share of the Economy |
| `commerce/pli.csv` | PLI Scheme Delivery (proxy) |
| `defence/capex.csv` | Defence Modernisation Budget (Share of Economy) |
| `defence/indigenisation.csv` | Defence Kit Bought from Indian Industry (proxy) |
| `defence/modernisation.csv` | Share of Equipment That Is Modern (proxy) |
| `education/learning.csv` | Children Reading at Grade Level (ASER) |
| `education/exam_integrity.csv` | Major Exam Paper Leaks & Cancellations (proxy) |
| `education/enrolment.csv` | Students Staying in School to Class 12 (UDISE+) |
| `skill/neet.csv` | Young People Not in Work, Education or Training |
| `skill/apprenticeship.csv` | Apprenticeship Budget Actually Spent |
| `skill/jobs.csv` | New Formal Jobs Added — EPFO (proxy) |
| `road/logistics_cost.csv` | Cost of Moving Goods (Share of Economy) (proxy) |
| `road/highway_pace.csv` | National Highway Built per Day |
| `road/modal_share.csv` | Freight Still Moving by Road (proxy) |

Generated (do not hand-edit): `GAPS.md`.

## Row format

Every row carries the KPI's formula inputs for one fiscal year **plus** the
standard provenance columns: `revision`, `source_doc`, `source_url`, `page_ref`,
`published_on`, `note`. Revision codes: `Actual` · `Provisional` · `Revised` ·
`BudgetEstimate` · `Estimated` (best compilation, not yet confirmed against the
primary document — listed in `GAPS.md`).

## Provenance / accuracy note

This snapshot was compiled from published official figures and, where no single
official series exists (industrial import dependence, PLI value-addition, defence
equipment vintage, exam-integrity incidents, pre-2022 logistics cost), from
assembled estimates that are **explicitly flagged `Estimated` and labelled as
proxies in the UI**. Confirm anything flagged `Estimated` / `BudgetEstimate`
against the cited primary document before treating the number as definitive.

## Refreshing

```bash
python -m app.tier_b_pipeline               # recompute all 15
python -m app.tier_b_pipeline --ministry EDU
```

`POST /sync` (the "Sync Live Data" button) runs this for you.
