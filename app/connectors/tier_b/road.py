"""Ministry of Road Transport & Highways (Logistics) — Tier-B connector.

KPIs:
  * logistics_cost_pct    — total logistics cost as % of GDP (proxy; methodology break)
  * highway_construction  — national highway km constructed per day
  * modal_share           — road's share of freight tonne-km (proxy)
"""

from __future__ import annotations

from app.connectors.tier_b.base import TierBConnector


class RoadConnector(TierBConnector):
    ministry_code = "ROAD"
    dataset_files = {
        "logistics_cost": "road/logistics_cost.csv",
        "highway_pace": "road/highway_pace.csv",
        "modal_share": "road/modal_share.csv",
    }
    valid_ranges = {
        "Logistics Cost %": (4.0, 18.0),
        "Highway Construction": (0.0, 60.0),
        "Modal Share": (40.0, 80.0),
    }

    def _compute_logistics_cost_pct(self, spec):
        return self._simple_series(
            spec,
            "logistics_cost",
            "logistics_cost_pct_gdp",
            formula="total logistics cost (transport + warehousing + inventory-carrying + losses + administration) / nominal GDP * 100 (NCAER-DPIIT methodology from FY2021-22; earlier years are legacy estimates)",
        )

    def _compute_highway_construction(self, spec):
        return self._simple_series(
            spec,
            "highway_pace",
            "km_per_day",
            formula="national highway km constructed in the year / days in the reporting period",
            secondary_col="total_km_constructed",
        )

    def _compute_modal_share(self, spec):
        return self._simple_series(
            spec,
            "modal_share",
            "road_share_pct",
            formula="road freight tonne-km / total inland freight tonne-km (road + rail + pipeline/coastal/IWT) * 100 ; secondary = rail share",
            secondary_col="rail_share_pct",
        )


def get_road_connector() -> RoadConnector:
    return RoadConnector()
