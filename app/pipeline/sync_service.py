from __future__ import annotations
import json
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.connectors.registry import get_connector
from app.models import KPIHistory, KPISource, Ministry
from app.pipeline.extractor import extract_raw_value
from app.pipeline.normalizer import clean_numeric


class SyncResult:
    """Outcome of checking one KPI's source."""

    def __init__(
        self,
        kpi_name: str,
        status: str,
        old_value: float | None = None,
        new_value: float | None = None,
        message: str = "",
        ministry_code: str = "",
    ):
        self.kpi_name = kpi_name
        self.status = status
        self.old_value = old_value
        self.new_value = new_value
        self.message = message
        self.ministry_code = ministry_code

    def __repr__(self) -> str:
        return f"<SyncResult {self.kpi_name}: {self.status} {self.old_value} -> {self.new_value}>"


def _sync_tier(db: Session, source: KPISource) -> SyncResult:
    """Recompute a Tier-A or Tier-B KPI from its curated data layer."""
    tier = source.source_type  # "tier_a" | "tier_b"
    if tier == "tier_b":
        from app.connectors.tier_b.spec import TIER_B_BY_KEY as BY_KEY
        from app.tier_b_pipeline import refresh_one
    else:
        from app.connectors.tier_a.spec import TIER_A_BY_KEY as BY_KEY
        from app.tier_a_pipeline import refresh_one

    kpi = source.kpi
    ministry_code = kpi.ministry.code
    cfg = source.parse_config if isinstance(source.parse_config, dict) else json.loads(source.parse_config or "{}")
    kpi_key = cfg.get("kpi_key") or (source.location.split(":", 1)[1] if ":" in source.location else "")
    spec = BY_KEY.get(kpi_key)
    if spec is None:
        return SyncResult(kpi.name, "error", message=f"unknown {tier} key {kpi_key!r}", ministry_code=ministry_code)

    old_value = kpi.current_value
    try:
        res = refresh_one(db, spec)
    except Exception as exc:  # noqa: BLE001
        return SyncResult(kpi.name, "error", message=f"{type(exc).__name__}: {exc}", ministry_code=ministry_code)

    status = {
        "updated": "updated",
        "unchanged": "no_change",
        "error": "error",
    }.get(res.status, res.status)
    return SyncResult(
        kpi.name, status, old_value, res.new_value, message=res.message, ministry_code=ministry_code
    )


def sync_kpi_source(db: Session, source: KPISource) -> SyncResult:
    kpi = source.kpi
    ministry_code = kpi.ministry.code

    if source.source_type in ("tier_a", "tier_b"):
        return _sync_tier(db, source)

    connector = get_connector(source.source_type)

    try:
        fetch_result = connector.fetch(source.location)
    except Exception as exc:
        return SyncResult(kpi.name, "error", message=f"fetch failed: {exc}", ministry_code=ministry_code)

    now = datetime.now(timezone.utc)
    source.last_checked_at = now

    if fetch_result.content_hash == source.last_hash:
        db.commit()
        return SyncResult(kpi.name, "unchanged_source", ministry_code=ministry_code)

    try:
        parse_config = (
            json.loads(source.parse_config)
            if isinstance(source.parse_config, str)
            else (source.parse_config or {})
        )
        records = connector.parse(fetch_result.raw, parse_config)
        raw_value = extract_raw_value(records, parse_config)
        new_value = clean_numeric(raw_value)
    except Exception as exc:
        db.commit()  # persist last_checked_at only; hash stays unchanged so a retry re-parses
        return SyncResult(kpi.name, "error", message=f"parse failed: {exc}", ministry_code=ministry_code)

    if new_value is None:
        db.commit()
        return SyncResult(
            kpi.name, "error", message="could not locate/parse value in source", ministry_code=ministry_code
        )

    # Only now that we have a usable value do we record the content hash.
    source.last_hash = fetch_result.content_hash
    source.last_changed_at = now

    old_value = kpi.current_value
    if old_value is not None and abs(new_value - old_value) < 1e-9:
        db.commit()
        return SyncResult(kpi.name, "no_change", old_value, new_value, ministry_code=ministry_code)

    kpi.current_value = new_value
    kpi.updated_at = now
    db.add(KPIHistory(kpi_id=kpi.id, value=new_value, recorded_at=now, source_hash=fetch_result.content_hash))
    db.commit()
    return SyncResult(kpi.name, "updated", old_value, new_value, ministry_code=ministry_code)


def sync_ministry(db: Session, ministry_code: str) -> list[SyncResult]:
    ministry = db.query(Ministry).filter(Ministry.code == ministry_code).first()
    if not ministry:
        raise ValueError(f"Unknown ministry code: {ministry_code}")
    results = []
    for kpi in ministry.kpis:
        if kpi.source is not None and kpi.source.is_active:
            results.append(sync_kpi_source(db, kpi.source))
    return results


def sync_all(db: Session) -> list[SyncResult]:
    sources = db.query(KPISource).filter(KPISource.is_active.is_(True)).all()
    return [sync_kpi_source(db, s) for s in sources]
