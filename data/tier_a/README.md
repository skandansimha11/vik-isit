# `data/tier_a/` — curated data layer for the 15 Tier-A KPIs

Every KPI for **Finance, Petroleum, Agriculture, Railways and Power** is computed
from the CSV files here. Nothing is scraped at runtime: these files *are* the
source of truth, and the connectors in `app/connectors/tier_a/` apply the
documented formula, validate, and build the dashboard series from them.

## File layout

| file | KPIs it feeds |
|---|---|
| `finance/fiscal.csv` | Fiscal Deficit |
| `finance/tax_revenue.csv` | Tax Collection Growth / Tax-to-GDP |
| `finance/tax_admin.csv` | Tax Harassment / Administrative Intensity (proxy) |
| `petroleum/crude.csv` | Oil Import Dependence |
| `petroleum/refining.csv` | Refining Efficiency |
| `_shared/ethanol.csv` | Ethanol Blending % (PETRO) **and** Ethanol Programme (AGRI) |
| `agriculture/farmer_income.csv` | Real Farmer Income (proxy) |
| `agriculture/cpi_food.csv` | Food Inflation |
| `railways/freight.csv` | Freight Volume Growth |
| `railways/modal_share.csv` | Rail Freight Modal Share |
| `railways/speed_capacity.csv` | Freight Speeds & Capacity |
| `power/industrial_tariffs.csv` | Industrial Tariffs |
| `power/discom.csv` | Discom AT&C Losses & Financial Health |
| `power/reliability.csv` | Power Availability |

Generated (do not hand-edit): `GAPS.md`, `SOURCES.md`, `.source_state.json`,
`.fetch_log.jsonl`.

## Row format

Every row has the KPI's formula inputs (columns vary per file — see the header)
**plus these provenance columns on every row**:

| column | meaning |
|---|---|
| `period` | `FY2019-20` for fiscal-year data, `ESY2019-20` for Ethanol Supply Year, `YYYY-MM` for monthly |
| `revision` | one of the codes below |
| `source_doc` | the exact document the figure is from |
| `source_url` | where that document lives |
| `page_ref` | table / page / section inside the document |
| `published_on` | `YYYY-MM` (or `YYYY-MM-DD`) the figure was published |
| `note` | methodology, cross-checks, caveats |

### Revision codes

| code | use |
|---|---|
| `Actual` | final audited/published figure — trusted |
| `Provisional` | published but not yet finalised (e.g. Provisional Actuals) |
| `Revised` | a Revised Estimate |
| `BudgetEstimate` | a Budget Estimate (forward-looking) |
| `Estimated` | our best compilation, **not yet confirmed against the primary document** |

`Estimated` and `BudgetEstimate` rows are listed in `GAPS.md`. When two rows
share a `period`, the one with the firmer revision wins.

## Refreshing

1. `python -m app.check_sources` — reports which KPIs' data is behind the latest
   official release and whether each source URL is reachable / changed. Writes
   `SOURCES.md`.
2. Open the CSV(s) for the KPI, add/replace rows from the cited `source_doc`,
   set `revision` honestly, update `published_on`.
3. `python -m app.tier_a_pipeline` — recomputes every KPI, rewrites the series,
   appends an audited history row where a value changed, regenerates `GAPS.md`.

`POST /sync` (the "Sync Live Data" button) runs step 3 for you.

## Provenance / accuracy note

This snapshot was compiled from published official figures. Rows flagged
`Estimated`/`BudgetEstimate` — and anything in `GAPS.md` — should be confirmed
against the cited primary document before the number is treated as definitive.
The proxy KPIs (Tax Harassment, Real Farmer Income) are model/assembly-based by
design and are labelled as such in the UI.
