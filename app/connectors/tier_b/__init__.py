"""Tier-B KPI connectors - provenance-tracked data for the 15 KPIs of the
Commerce & Industry, Defence, Education, Skill Development & Labour, and Road
Transport & Highways ministries.

Mirror of :mod:`app.connectors.tier_a`:

    from app.connectors.tier_b import get_tier_b_connector, TIER_B_KPIS, compute_kpi
"""

from __future__ import annotations

from app.connectors.tier_a.base import KPISeries, SeriesPoint
from app.connectors.tier_b.spec import (
    TIER_B_BY_KEY,
    TIER_B_BY_NAME,
    TIER_B_KPIS,
    TIER_B_MINISTRIES,
)


def get_tier_b_connector(ministry_code: str):
    """Always returns a FRESH connector instance (see the Tier-A note - a
    long-running server otherwise serves stale CSV contents on /sync)."""
    code = ministry_code.upper()

    from app.connectors.tier_b.commerce import CommerceConnector
    from app.connectors.tier_b.defence import DefenceConnector
    from app.connectors.tier_b.education import EducationConnector
    from app.connectors.tier_b.road import RoadConnector
    from app.connectors.tier_b.skill import SkillConnector

    registry = {
        "COMM": CommerceConnector,
        "DEF": DefenceConnector,
        "EDU": EducationConnector,
        "SKILL": SkillConnector,
        "ROAD": RoadConnector,
    }
    if code not in registry:
        raise ValueError(f"no Tier-B connector for ministry {ministry_code!r}")
    return registry[code]()


def compute_kpi(kpi_key: str) -> KPISeries:
    spec = TIER_B_BY_KEY.get(kpi_key)
    if spec is None:
        raise ValueError(f"unknown Tier-B KPI key {kpi_key!r}")
    connector = get_tier_b_connector(spec.ministry_code)
    return connector.compute(spec)


__all__ = [
    "KPISeries",
    "SeriesPoint",
    "TIER_B_KPIS",
    "TIER_B_BY_KEY",
    "TIER_B_BY_NAME",
    "TIER_B_MINISTRIES",
    "get_tier_b_connector",
    "compute_kpi",
]
