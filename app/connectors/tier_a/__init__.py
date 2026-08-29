"""Tier-A KPI connectors — real, provenance-tracked data for the 15 KPIs of
the Finance, Petroleum, Agriculture, Railways and Power ministries.

Public surface:

    from app.connectors.tier_a import get_tier_a_connector, TIER_A_KPIS, compute_kpi

``get_tier_a_connector(ministry_code)`` -> the ministry's connector instance.
``compute_kpi(kpi_key)`` -> a :class:`~app.connectors.tier_a.base.KPISeries`.
``TIER_A_KPIS`` -> the 15 :class:`~app.connectors.tier_a.spec.TierAKpi` specs.
"""

from __future__ import annotations

from app.connectors.tier_a.base import KPISeries, SeriesPoint
from app.connectors.tier_a.spec import TIER_A_KPIS, TIER_A_BY_KEY, TIER_A_BY_NAME, TierAKpi

def get_tier_a_connector(ministry_code: str):
    """Always returns a FRESH connector instance — its curated datasets are
    loaded lazily and cached per-instance, so a fresh instance guarantees the
    latest CSV contents (important for a long-running server handling /sync)."""
    code = ministry_code.upper()

    from app.connectors.tier_a.agriculture import AgricultureConnector
    from app.connectors.tier_a.finance import FinanceConnector
    from app.connectors.tier_a.petroleum import PetroleumConnector
    from app.connectors.tier_a.power import PowerConnector
    from app.connectors.tier_a.railways import RailwaysConnector

    registry = {
        "FIN": FinanceConnector,
        "PETRO": PetroleumConnector,
        "AGRI": AgricultureConnector,
        "RAIL": RailwaysConnector,
        "POW": PowerConnector,
    }
    if code not in registry:
        raise ValueError(f"no Tier-A connector for ministry {ministry_code!r}")
    return registry[code]()


def compute_kpi(kpi_key: str) -> KPISeries:
    spec = TIER_A_BY_KEY.get(kpi_key)
    if spec is None:
        raise ValueError(f"unknown Tier-A KPI key {kpi_key!r}")
    connector = get_tier_a_connector(spec.ministry_code)
    return connector.compute(spec)


__all__ = [
    "KPISeries",
    "SeriesPoint",
    "TIER_A_KPIS",
    "TIER_A_BY_KEY",
    "TIER_A_BY_NAME",
    "TierAKpi",
    "get_tier_a_connector",
    "compute_kpi",
]
