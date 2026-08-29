from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from sqlalchemy.orm import Session

from app.models import KPI, KPISource, Ministry

MINISTRIES_DIR = Path(__file__).parent / "ministries"


def load_config_file(path: Path) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def upsert_ministry(db: Session, config: dict[str, Any]) -> Ministry:
    """Create or update a Ministry, its KPIs, and their data sources from a
    config dict. Safe to re-run: matches on ministry code and KPI name."""
    m_cfg = config["ministry"]
    ministry = db.query(Ministry).filter(Ministry.code == m_cfg["code"]).first()
    if ministry is None:
        ministry = Ministry(
            name=m_cfg["name"], code=m_cfg["code"], description=m_cfg.get("description", "")
        )
        db.add(ministry)
        db.flush()
    else:
        ministry.name = m_cfg["name"]
        ministry.description = m_cfg.get("description", "")

    for kpi_cfg in config.get("kpis", []):
        kpi = (
            db.query(KPI)
            .filter(KPI.ministry_id == ministry.id, KPI.name == kpi_cfg["name"])
            .first()
        )
        if kpi is None:
            kpi = KPI(
                ministry_id=ministry.id,
                name=kpi_cfg["name"],
                category=kpi_cfg.get("category", "general"),
                unit=kpi_cfg.get("unit", ""),
                current_value=0.0,
                target_value=kpi_cfg.get("target_value", 0.0),
                period=kpi_cfg.get("period", ""),
            )
            db.add(kpi)
            db.flush()
        else:
            kpi.category = kpi_cfg.get("category", kpi.category)
            kpi.unit = kpi_cfg.get("unit", kpi.unit)
            kpi.target_value = kpi_cfg.get("target_value", kpi.target_value)
            kpi.period = kpi_cfg.get("period", kpi.period)

        src_cfg = kpi_cfg.get("source")
        if not src_cfg:
            continue

        parse_config = {k: v for k, v in src_cfg.items() if k not in {"type", "location"}}
        if kpi.source is None:
            kpi.source = KPISource(
                kpi_id=kpi.id,
                source_type=src_cfg["type"],
                location=src_cfg["location"],
                parse_config=parse_config,
            )
            db.add(kpi.source)
        else:
            kpi.source.source_type = src_cfg["type"]
            kpi.source.location = src_cfg["location"]
            kpi.source.parse_config = parse_config

    db.commit()
    return ministry


def load_all_configs(db: Session) -> list[Ministry]:
    return [
        upsert_ministry(db, load_config_file(path)) for path in sorted(MINISTRIES_DIR.glob("*.yaml"))
    ]
