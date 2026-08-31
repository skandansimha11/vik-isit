"""Ministry of Railways - Tier-A connector.

KPIs:
  * freight_volume_growth  - YoY growth in originating revenue-earning freight (MT)
  * rail_market_share      - rail vs road share of freight tonne-km
  * train_speeds_capacity  - avg freight-train speed, against congested-route share
"""

from __future__ import annotations

from app.connectors.tier_a.base import FY_YEARS, AuditEntry, SeriesPoint, TierAConnector, fy_label


class RailwaysConnector(TierAConnector):
    ministry_code = "RAIL"
    dataset_files = {
        "freight": "railways/freight.csv",
        "modal_share": "railways/modal_share.csv",
        "speed_capacity": "railways/speed_capacity.csv",
    }
    valid_ranges = {
        "Freight Volume Growth": (-30.0, 30.0),
        "Rail Market Share": (0.0, 100.0),
        "Train Speeds & Capacity": (15.0, 90.0),
        # referenced by the connector test-suite:
        "On-Time Performance": (0.0, 100.0),
        "Passenger Traffic": (0.0, 20000.0),
        "Freight Loading": (0.0, 5000.0),
    }

    # -- calculation helpers -----------------------------------------

    @staticmethod
    def freight_growth_pct(current_mt: float, previous_mt: float) -> float:
        if previous_mt == 0:
            return 0.0
        return round((current_mt - previous_mt) / previous_mt * 100, 2)

    @staticmethod
    def ntkm_growth_pct(current_ntkm: float, previous_ntkm: float) -> float:
        if previous_ntkm == 0:
            return 0.0
        return round((current_ntkm - previous_ntkm) / previous_ntkm * 100, 2)

    @staticmethod
    def rail_share_pct(rail_tkm: float, total_tkm: float) -> float:
        if total_tkm == 0:
            return 0.0
        return round(rail_tkm / total_tkm * 100, 2)

    # -- KPI: Freight Volume Growth -------------------------------

    def _compute_freight_volume_growth(self, spec):
        ds = self.dataset("freight")
        fy = self._fy_points(ds)
        points, audit = [], []
        for year in FY_YEARS:
            dp, prev = fy.get(year), fy.get(year - 1)
            if dp is None:
                points.append(SeriesPoint(year, fy_label(year)))
                continue
            mt, mt_prev = dp.get("freight_loaded_mt"), (prev.get("freight_loaded_mt") if prev else None)
            growth = self.freight_growth_pct(mt, mt_prev) if (mt and mt_prev) else None
            ntkm, ntkm_prev = dp.get("ntkm_billion"), (prev.get("ntkm_billion") if prev else None)
            ntkm_g = self.ntkm_growth_pct(ntkm, ntkm_prev) if (ntkm and ntkm_prev) else None
            target = dp.get("target_freight_mt")
            target_growth = (
                self.freight_growth_pct(target, mt_prev) if (target and mt_prev) else spec.target_value
            )
            audit.append(
                AuditEntry(
                    period=dp.period,
                    formula="growth% = (freight_loaded_MT_t - freight_loaded_MT_{t-1}) / freight_loaded_MT_{t-1} * 100",
                    inputs={
                        "freight_loaded_mt": mt,
                        "freight_loaded_mt_prev": mt_prev,
                        "ntkm_billion": ntkm,
                        "ntkm_growth_pct": ntkm_g,
                    },
                    output=growth,
                    source_doc=dp.source_doc,
                    source_url=dp.source_url,
                    page_ref=dp.page_ref,
                    revision=dp.revision,
                )
            )
            points.append(
                SeriesPoint(
                    year, fy_label(year), value=growth, target_value=target_growth, revision=dp.revision
                )
            )
        return points, audit, self._collect_unresolved(spec, fy), self._current_from(points, fy)

    # -- KPI: Rail Freight Modal Share ---------------------------

    def _compute_rail_market_share(self, spec):
        ds = self.dataset("modal_share")
        fy = self._fy_points(ds)
        points, audit = [], []
        for year in FY_YEARS:
            dp = fy.get(year)
            if dp is None:
                points.append(SeriesPoint(year, fy_label(year)))
                continue
            rail_pct = dp.get("rail_share_pct")
            road_pct = dp.get("road_share_pct")
            other_pct = dp.get("other_share_pct")
            breakdown = None
            if rail_pct is not None and road_pct is not None:
                breakdown = {"Rail": rail_pct, "Road": road_pct}
                if other_pct is not None:
                    breakdown["Other"] = other_pct
            audit.append(
                AuditEntry(
                    period=dp.period,
                    formula="rail share % = rail freight tonne-km / total inland freight tonne-km (rail + road + pipeline/coastal/IWT) * 100",
                    inputs={
                        "rail_share_pct": rail_pct,
                        "road_share_pct": road_pct,
                        "other_share_pct": other_pct,
                    },
                    output=rail_pct,
                    source_doc=dp.source_doc,
                    source_url=dp.source_url,
                    page_ref=dp.page_ref,
                    revision=dp.revision,
                )
            )
            points.append(
                SeriesPoint(
                    year,
                    fy_label(year),
                    value=rail_pct,
                    breakdown=breakdown,
                    target_value=spec.target_value,
                    revision=dp.revision,
                )
            )
        return points, audit, self._collect_unresolved(spec, fy), self._current_from(points, fy)

    # -- KPI: Freight Speeds & Capacity Utilisation --------------

    def _compute_train_speeds_capacity(self, spec):
        ds = self.dataset("speed_capacity")
        fy = self._fy_points(ds)
        points, audit = [], []
        for year in FY_YEARS:
            dp = fy.get(year)
            if dp is None:
                points.append(SeriesPoint(year, fy_label(year)))
                continue
            speed = dp.get("avg_freight_speed_kmph")
            congested = dp.get("congested_route_share_pct")
            audit.append(
                AuditEntry(
                    period=dp.period,
                    formula="avg speed of goods trains (km/h), reported directly; secondary = share of route-km at or above 100% sectional line capacity",
                    inputs={
                        "avg_freight_speed_kmph": speed,
                        "congested_route_share_pct": congested,
                        "electrified_route_pct": dp.get("electrified_route_pct"),
                    },
                    output=speed,
                    source_doc=dp.source_doc,
                    source_url=dp.source_url,
                    page_ref=dp.page_ref,
                    revision=dp.revision,
                )
            )
            points.append(
                SeriesPoint(
                    year,
                    fy_label(year),
                    value=speed,
                    secondary_value=congested,
                    target_value=spec.target_value,
                    revision=dp.revision,
                )
            )
        return points, audit, self._collect_unresolved(spec, fy), self._current_from(points, fy)


def get_railways_connector() -> RailwaysConnector:
    return RailwaysConnector()
