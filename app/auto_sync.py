"""Daily automation layer on top of app.check_sources.

    python -m app.auto_sync

What it does, in order:
  1. Runs the existing freshness check (app.check_sources) across both tiers -
     this is still the single source of truth for "is this KPI behind schedule".
  2. For every KPI that's behind, tries a Tier-A auto-fetcher
     (app.connectors.tier_a.fetchers). A fetcher may ONLY write a CSV row when
     it has an unambiguous, validated number (strict type/shape check, inside
     the KPI's valid_range, never overwriting an Actual/Revised row) - see the
     contract in that module. Everything else stays untouched; auto_sync never
     writes a KPI value itself.
  3. Whatever a fetcher could NOT safely resolve is written to
     data/PENDING_UPDATES.md - one file, one entry per KPI, with the exact CSV
     path, the exact columns that file expects, and the source to read the
     number from. The goal is that updating a KPI by hand is "open the source,
     read one number, fill one CSV row", not "rediscover which file, which
     columns, which source" from scratch.

This module only touches files on disk (CSVs + PENDING_UPDATES.md). It never
touches the database or the live site - see .github/workflows/auto-data-sync.yml
for how a CI run turns a successful auto-fetch into a live update (commit the
CSV change -> Render redeploys with it baked in -> the workflow calls POST
/sync on the live API so the database, scores and verdicts catch up).
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from pathlib import Path

from app.check_sources import TIERS, run as run_check_sources
from app.connectors.provenance import PROVENANCE_COLUMNS, DATA_ROOT

PENDING_PATH = DATA_ROOT.parent / "PENDING_UPDATES.md"

# Maps a Tier-A KPI `key` (app.connectors.tier_a.spec) to the auto-fetcher that
# might be able to resolve it (app.connectors.tier_a.fetchers.ALL). Not every
# stale KPI has an entry here - only the ones with *any* machine-approachable
# source at all. Extending real automation to another KPI means: (a) write a
# fetcher in app/connectors/tier_a/fetchers/ that returns a validated number or
# ok=False, nothing in between, and (b) add its key here.
FETCHER_FOR_KEY = {
    "oil_import_dependence": "ppac_snapshot",
    "ethanol_blending": "ppac_snapshot",
    "refining_efficiency": "ppac_snapshot",
    "food_inflation": "mospi_cpi",
    "freight_volume_growth": "pib_rail_freight",
}


@dataclass
class AutoSyncReport:
    checked: int = 0
    stale: int = 0
    auto_written: list[str] = field(default_factory=list)  # "FIN · Fiscal Deficit"
    needs_human: list[dict] = field(default_factory=list)
    fetch_log: list[dict] = field(default_factory=list)

    @property
    def any_written(self) -> bool:
        return bool(self.auto_written)

    @property
    def any_pending(self) -> bool:
        return bool(self.needs_human)

    def summary_line(self) -> str:
        return (
            f"{self.checked} KPI(s) checked, {self.stale} stale, "
            f"{len(self.auto_written)} auto-updated, {len(self.needs_human)} need a human"
        )


def _append_provisional_row(csv_path: Path, period: str, values: dict, source_doc: str, source_url: str, note: str) -> bool:
    """Append one Provisional row to a curated CSV, matching its existing header
    exactly. Returns False (writes nothing) if the file doesn't have columns for
    every key in `values` - a schema mismatch must never produce a malformed row."""
    if not csv_path.exists():
        return False
    with csv_path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.reader(fh)
        header = next(reader, None)
        rows = list(reader)
    if not header:
        return False
    value_cols = [c for c in header if c not in ("period", *PROVENANCE_COLUMNS)]
    if any(v not in header for v in values):
        return False
    row_map = {c: "" for c in header}
    row_map["period"] = period
    for k, v in values.items():
        row_map[k] = v
    row_map["revision"] = "Provisional"
    row_map["source_doc"] = source_doc
    row_map["source_url"] = source_url
    import datetime

    row_map["published_on"] = datetime.date.today().strftime("%Y-%m")
    row_map["note"] = note
    # Replace an existing row for the same period only if it's also Provisional-
    # or-softer (never clobber Actual/Revised/BudgetEstimate curated by a human).
    out_rows = [r for r in rows if not (len(r) >= 1 and r[0] == period)]
    existing = next((r for r in rows if len(r) >= 1 and r[0] == period), None)
    if existing is not None:
        existing_rev = existing[header.index("revision")] if "revision" in header else ""
        if existing_rev not in ("", "Provisional", "Estimated"):
            return False  # a firmer row already covers this period - don't touch it
    out_rows.append([row_map[c] for c in header])
    with csv_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(header)
        writer.writerows(out_rows)
    return True


def _try_fetch(key: str, spec, root: Path, dataset_rel: str) -> tuple[bool, dict]:
    from app.connectors.tier_a import fetchers

    fetcher_name = FETCHER_FOR_KEY.get(key)
    if fetcher_name is None:
        return False, {"ok": False, "summary": "no auto-fetcher wired for this KPI yet"}
    fn = fetchers.ALL.get(fetcher_name)
    if fn is None:
        return False, {"ok": False, "summary": f"fetcher {fetcher_name!r} not found"}
    try:
        result = fn()
    except Exception as exc:  # noqa: BLE001 - a fetcher must never take the run down
        return False, {"ok": False, "summary": f"{fetcher_name} raised: {exc}"}

    if not result.get("ok") or not result.get("wrote"):
        return False, result

    wrote_any = False
    for item in result["wrote"]:
        csv_path = (root / dataset_rel) if not Path(dataset_rel).is_absolute() else Path(dataset_rel)
        if _append_provisional_row(
            csv_path,
            period=item["period"],
            values=item["values"],
            source_doc=item.get("source_doc", spec.source_name),
            source_url=item.get("source_url", spec.source_url),
            note=item.get("note", f"auto-fetched by {fetcher_name}"),
        ):
            wrote_any = True
    return wrote_any, result


def run() -> AutoSyncReport:
    report = AutoSyncReport()
    rows = run_check_sources(tiers="ab")
    report.checked = len(rows)

    by_key = {}
    for tier_letter, cfg in TIERS.items():
        for spec in cfg["kpis"]:
            by_key[spec.key] = (tier_letter, spec, cfg["root"])

    for row in rows:
        if row["action"] == "ok":
            continue
        report.stale += 1
        key = row["key"]
        entry = by_key.get(key)
        if entry is None:
            continue
        tier_letter, spec, root = entry

        if tier_letter == "a" and key in FETCHER_FOR_KEY:
            from app.connectors.tier_a import get_tier_a_connector

            conn = get_tier_a_connector(spec.ministry_code)
            dataset_rel = next(iter(conn.dataset_files.values())) if spec.datasets else None
            # resolve the actual configured relative path(s) for this spec's datasets
            dataset_rels = [conn.dataset_files[d] for d in spec.datasets if d in conn.dataset_files]
            written = False
            fetch_result = {"ok": False, "summary": "no dataset path resolved"}
            for rel in dataset_rels:
                w, fetch_result = _try_fetch(key, spec, root, rel)
                written = written or w
            report.fetch_log.append({"key": key, **fetch_result})
            if written:
                report.auto_written.append(f"{row['ministry']} · {row['kpi']}")
                continue

        report.needs_human.append(row)

    _write_pending_updates(report)
    return report


def _write_pending_updates(report: AutoSyncReport) -> None:
    if not report.needs_human:
        if PENDING_PATH.exists():
            PENDING_PATH.write_text(
                "# Pending data updates\n\nNothing needs attention right now - every tracked KPI "
                "is either current or was just auto-updated.\n",
                encoding="utf-8",
            )
        return

    lines = [
        "# Pending data updates",
        "",
        "Generated by `python -m app.auto_sync`. Each entry below could not be updated",
        "automatically (no fetcher wired, or the source didn't return an unambiguous",
        "number) - open the source, read the latest figure, and add one row to the",
        "listed CSV. Then run `python -m app.tier_a_pipeline` (or `tier_b_pipeline`) and",
        "commit. This file is regenerated every run; editing it directly has no effect.",
        "",
    ]
    for row in report.needs_human:
        tier_key = "a" if row["tier"] == "Tier-A" else "b"
        cfg = TIERS[tier_key]
        spec = next(s for s in cfg["kpis"] if s.key == row["key"])
        from app.connectors.tier_a import get_tier_a_connector
        from app.connectors.tier_b import get_tier_b_connector

        conn = (get_tier_a_connector if tier_key == "a" else get_tier_b_connector)(spec.ministry_code)
        rels = [conn.dataset_files[d] for d in spec.datasets if d in conn.dataset_files]
        have = f"FY{row['data_through_fy']}-{str(row['data_through_fy'] + 1)[2:]}" if row["data_through_fy"] else "nothing yet"
        lines.append(f"## {row['ministry']} · {row['kpi']}")
        lines.append("")
        lines.append(f"- **Why it's listed:** {row['action']}")
        lines.append(f"- **Have data through:** {have}")
        lines.append(f"- **Source:** [{row['source_name']}]({row['source_url']}) ({row['cadence']})")
        for rel in rels:
            path = cfg["root"] / rel
            cols = "(file not found yet)"
            if path.exists():
                with path.open("r", encoding="utf-8-sig") as fh:
                    header = next(csv.reader(fh), [])
                cols = ", ".join(header)
            lines.append(f"- **File:** `{path.relative_to(DATA_ROOT.parent.parent)}` - columns: `{cols}`")
        lines.append("")

    PENDING_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    report = run()
    print(report.summary_line())
    if report.auto_written:
        print("\nAuto-updated:")
        for w in report.auto_written:
            print(f"  - {w}")
    if report.needs_human:
        print(f"\n{len(report.needs_human)} KPI(s) written to {PENDING_PATH.name} for a human to fill in.")
    # Machine-readable summary for the GitHub Actions step that calls this.
    print("::auto-sync-json::" + json.dumps({
        "checked": report.checked,
        "stale": report.stale,
        "auto_written": report.auto_written,
        "pending": len(report.needs_human),
    }))


if __name__ == "__main__":
    main()
