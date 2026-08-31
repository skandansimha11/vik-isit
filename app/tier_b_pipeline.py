"""Recompute the 15 Tier-B KPIs (Commerce & Industry, Defence, Education, Skill
Development & Labour, Road Transport & Highways) from the curated
``data/tier_b/`` layer and write the results to the DB.

    python -m app.tier_b_pipeline                 # refresh all 15
    python -m app.tier_b_pipeline --ministry COMM
    python -m app.tier_b_pipeline --kpi manufacturing_growth
    python -m app.tier_b_pipeline --dry-run

Mirror of ``app/tier_a_pipeline.py`` - same behaviour, same idempotency
(a KPIHistory row is appended only when ``current_value`` moves). Run *after*
``python -m app.seed_dashboard`` (which creates the KPI rows).
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.connectors.provenance import TIER_B_ROOT, combined_hash, load_dataset
from app.connectors.tier_b import TIER_B_KPIS, compute_kpi, get_tier_b_connector
from app.connectors.tier_b.spec import TIER_B_BY_KEY, TierAKpi
from app.connectors.tier_a.base import KPISeries
from app.database import Base, SessionLocal, engine, sync_schema
from app.models import KPI, KPIHistory, KPISeriesPoint, KPISource, Ministry

GAPS_PATH = TIER_B_ROOT / "GAPS.md"
SOURCE_TYPE = "tier_b"


class RefreshResult:
    def __init__(self, kpi_key: str, kpi_name: str, ministry: str):
        self.kpi_key = kpi_key
        self.kpi_name = kpi_name
        self.ministry = ministry
        self.status = "skipped"
        self.old_value: float | None = None
        self.new_value: float | None = None
        self.revision = ""
        self.points = 0
        self.soft_points = 0
        self.message = ""
        self.series: KPISeries | None = None


def _dataset_hash_for(spec: TierAKpi) -> str:
    conn = get_tier_b_connector(spec.ministry_code)
    files = [conn.dataset_files[k] for k in spec.datasets if k in conn.dataset_files]
    return combined_hash([load_dataset(f, root=TIER_B_ROOT) for f in files])


def _apply_presentation(kpi: KPI, spec: TierAKpi) -> None:
    kpi.chart_type = spec.chart_type
    kpi.data_shape = spec.data_shape
    kpi.unit = spec.unit
    kpi.higher_is_better = spec.higher_is_better
    kpi.target_value = spec.target.official if spec.target.official is not None else 0.0
    kpi.aspirational_target = spec.target.aspirational
    kpi.benchmark_label = spec.target.official_label
    kpi.aspirational_label = spec.target.aspirational_label
    kpi.secondary_label = spec.secondary_label
    kpi.secondary_unit = spec.secondary_unit
    kpi.breakdown_label = spec.breakdown_label
    kpi.display_title = spec.display_title
    kpi.plain_note = spec.plain_note


def _write_series(db: Session, kpi: KPI, series: KPISeries) -> None:
    db.query(KPISeriesPoint).filter(KPISeriesPoint.kpi_id == kpi.id).delete()
    for p in series.points:
        db.add(
            KPISeriesPoint(
                kpi_id=kpi.id,
                year=p.year,
                period_label=p.period_label,
                value=p.value,
                secondary_value=p.secondary_value,
                target_value=p.target_value,
                breakdown=p.breakdown,
                revision=p.revision,
            )
        )


def _upsert_source(db: Session, kpi: KPI, spec: TierAKpi, series: KPISeries, content_hash: str) -> None:
    now = datetime.now(timezone.utc)
    src = kpi.source
    if src is None:
        src = KPISource(kpi_id=kpi.id, source_type=SOURCE_TYPE, location=f"{spec.ministry_code}:{spec.key}")
        db.add(src)
        kpi.source = src
    src.source_type = SOURCE_TYPE
    src.location = f"{spec.ministry_code}:{spec.key}"
    src.parse_config = {"kpi_key": spec.key, "datasets": list(spec.datasets)}
    src.is_active = True
    src.is_live = True
    src.data_quality = series.data_quality
    src.is_proxy = series.is_proxy
    src.data_version = series.current_revision or "Provisional"
    src.source_name = series.source_name
    src.source_url = series.source_url
    src.source_cadence = spec.cadence
    src.source_updated_at = series.source_updated_at
    src.last_hash = content_hash
    src.last_checked_at = now
    src.last_changed_at = now


def _append_history(db: Session, kpi: KPI, series: KPISeries, content_hash: str) -> bool:
    new_val = series.current_value
    if new_val is None:
        return False
    prev = (
        db.query(KPIHistory)
        .filter(KPIHistory.kpi_id == kpi.id)
        .order_by(KPIHistory.recorded_at.desc())
        .first()
    )
    if prev is not None and abs(prev.value - new_val) < 1e-9:
        return False

    latest_audit = series.audit[-1] if series.audit else None
    formula = latest_audit.formula if latest_audit else ""
    audit_blob = json.dumps(
        {
            "kpi_key": series.kpi_key,
            "current_period": series.current_period,
            "current_revision": series.current_revision,
            "per_period": [
                {
                    "period": a.period,
                    "formula": a.formula,
                    "inputs": a.inputs,
                    "output": a.output,
                    "source_doc": a.source_doc,
                    "source_url": a.source_url,
                    "page_ref": a.page_ref,
                    "revision": a.revision,
                }
                for a in series.audit
            ],
        },
        default=str,
    )
    confidence = {"HIGH": 90, "MEDIUM": 70, "LOW": 45}.get(series.data_quality, 60)
    if series.current_revision in ("Estimated", "BudgetEstimate", ""):
        confidence = min(confidence, 50)

    db.add(
        KPIHistory(
            kpi_id=kpi.id,
            value=new_val,
            recorded_at=datetime.now(timezone.utc),
            source_hash=content_hash,
            source_url=series.source_url,
            data_version=series.current_revision or "Provisional",
            extraction_confidence=confidence,
            calculation_formula=formula[:500],
            audit_log=audit_blob,
        )
    )
    return True


def _clear_stale_hashes(db: Session, kpi_keys: set[str]) -> None:
    names = {TIER_B_BY_KEY[k].name for k in kpi_keys if k in TIER_B_BY_KEY}
    for src in db.query(KPISource).all():
        if src.kpi and src.kpi.name in names and src.source_type != SOURCE_TYPE:
            src.last_hash = None
            src.is_active = False
    db.commit()


def refresh_one(db: Session, spec: TierAKpi, *, dry_run: bool = False) -> RefreshResult:
    res = RefreshResult(spec.key, spec.name, spec.ministry_code)
    ministry = db.query(Ministry).filter(Ministry.code == spec.ministry_code).first()
    if ministry is None:
        res.status = "error"
        res.message = f"ministry {spec.ministry_code} not seeded - run `python -m app.seed_dashboard` first"
        return res
    kpi = db.query(KPI).filter(KPI.ministry_id == ministry.id, KPI.name == spec.name).first()
    if kpi is None:
        res.status = "error"
        res.message = f"KPI {spec.name!r} not found under {spec.ministry_code} - run seed_dashboard first"
        return res

    try:
        series = compute_kpi(spec.key)
    except Exception as exc:  # noqa: BLE001 - surfaced in the report
        res.status = "error"
        res.message = f"{type(exc).__name__}: {exc}"
        return res

    res.series = series
    res.old_value = kpi.current_value
    res.new_value = series.current_value
    res.revision = series.current_revision
    res.points = sum(1 for p in series.points if p.value is not None or p.breakdown)
    res.soft_points = len(series.unresolved)

    if dry_run:
        res.status = "dry-run"
        return res

    content_hash = _dataset_hash_for(spec)
    _apply_presentation(kpi, spec)
    if series.current_value is not None:
        kpi.current_value = series.current_value
    if series.current_period:
        y = series.current_period.replace("FY", "").replace("ESY", "")
        kpi.period = f"FY {y}" if "-" in y else series.current_period
    kpi.updated_at = datetime.now(timezone.utc)
    _write_series(db, kpi, series)
    _upsert_source(db, kpi, spec, series, content_hash)
    appended = _append_history(db, kpi, series, content_hash)
    db.commit()

    res.status = "updated" if appended else "unchanged"
    return res


def write_gaps(all_series: list[KPISeries]) -> int:
    lines = [
        "# Tier-B data gaps - figures pending confirmation",
        "",
        "Generated by `python -m app.tier_b_pipeline`. Every row below is flagged",
        "`Estimated` / `BudgetEstimate` or has a missing formula input. Confirm each",
        "against the cited primary document and update the CSV under `data/tier_b/`,",
        "then re-run the pipeline.",
        "",
    ]
    total = 0
    for s in sorted(all_series, key=lambda x: (x.ministry_code, x.kpi_name)):
        if not s.unresolved:
            continue
        lines.append(f"## {s.ministry_code} · {s.kpi_name}  ({s.data_quality}{', PROXY' if s.is_proxy else ''})")
        lines.append("")
        lines.append("| period | dataset row | revision | reason | source document | page/table |")
        lines.append("|---|---|---|---|---|---|")
        for u in s.unresolved:
            total += 1
            lines.append(
                f"| {u['period']} | {u['dataset']}:{u['row']} | {u['revision']} | {u['reason']} | "
                f"{u['source_doc']} | {u['page_ref']} |"
            )
        lines.append("")
    lines.append(f"_Total unresolved data points: {total}_")
    GAPS_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return total


def refresh_tier_b(
    db: Session, *, ministry: str | None = None, kpi_key: str | None = None, dry_run: bool = False
) -> list[RefreshResult]:
    specs = list(TIER_B_KPIS)
    if ministry:
        specs = [s for s in specs if s.ministry_code == ministry.upper()]
    if kpi_key:
        specs = [s for s in specs if s.key == kpi_key]
    if not specs:
        raise ValueError("no Tier-B KPIs matched the filter")

    _clear_stale_hashes(db, {s.key for s in specs})

    results: list[RefreshResult] = []
    all_series: list[KPISeries] = []
    for spec in specs:
        r = refresh_one(db, spec, dry_run=dry_run)
        results.append(r)
        if r.series is not None:
            all_series.append(r.series)

    if not dry_run and len(specs) == len(TIER_B_KPIS):
        gaps = write_gaps(all_series)
        print(f"\nWrote {GAPS_PATH.relative_to(Path.cwd())} - {gaps} unresolved data point(s).")

    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Recompute Tier-B KPIs from data/tier_b/.")
    parser.add_argument("--ministry", help="restrict to one ministry code (COMM/DEF/EDU/SKILL/ROAD)")
    parser.add_argument("--kpi", dest="kpi_key", help="restrict to one KPI key")
    parser.add_argument("--dry-run", action="store_true", help="compute + report, write nothing")
    args = parser.parse_args()

    Base.metadata.create_all(bind=engine)
    sync_schema()
    db = SessionLocal()
    try:
        results = refresh_tier_b(db, ministry=args.ministry, kpi_key=args.kpi_key, dry_run=args.dry_run)
    finally:
        db.close()

    print(f"\nTier-B refresh - {len(results)} KPI(s){' (dry-run)' if args.dry_run else ''}:")
    print(f"  {'ministry':<8} {'KPI':<28} {'status':<10} {'value':>10} {'rev':<14} pts  gaps")
    for r in results:
        val = "-" if r.new_value is None else f"{r.new_value:.2f}"
        print(
            f"  {r.ministry:<8} {r.kpi_name:<28} {r.status:<10} {val:>10} "
            f"{r.revision:<14} {r.points:>3}  {r.soft_points:>3}"
        )
        if r.message:
            print(f"           └─ {r.message}")

    errors = sum(1 for r in results if r.status == "error")
    updated = sum(1 for r in results if r.status == "updated")
    print(f"\n{updated} updated, {len(results) - updated - errors} unchanged, {errors} error(s).")
    if errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
