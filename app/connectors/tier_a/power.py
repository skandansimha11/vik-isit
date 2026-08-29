"""Ministry of Power — Tier-A connector.

KPIs:
  * industrial_tariffs         — avg industrial tariff ₹/kWh, national + major states
  * discom_financial_health    — AT&C loss %, against ACS-ARR gap ₹/kWh
  * power_availability          — energy availability % (supplied ÷ requirement)
"""

from __future__ import annotations

from app.connectors.tier_a.base import FY_YEARS, AuditEntry, SeriesPoint, TierAConnector, fy_label


class PowerConnector(TierAConnector):
    ministry_code = "POW"
    dataset_files = {
        "industrial_tariffs": "power/industrial_tariffs.csv",
        "discom": "power/discom.csv",
        "reliability": "power/reliability.csv",
    }
    valid_ranges = {
        "Industrial Tariffs": (2.0, 15.0),
        "Discom Financial Health": (5.0, 45.0),
        "Power Availability": (85.0, 100.0),
        # referenced by the connector test-suite:
        "Transmission & Distribution Losses": (0.0, 45.0),
        "Installed Renewable Energy Capacity": (0.0, 1000.0),
        "Per Capita Electricity Consumption": (0.0, 5000.0),
    }

    # -- calculation helpers -----------------------------------------

    @staticmethod
    def calculate_atc_losses_pct(energy_input_units_mu: float, energy_billed_realised_units_mu: float) -> float:
        if energy_input_units_mu == 0:
            return 0.0
        return round((energy_input_units_mu - energy_billed_realised_units_mu) / energy_input_units_mu * 100, 2)

    @staticmethod
    def acs_arr_gap(acs_rs_kwh: float, arr_rs_kwh: float) -> float:
        return round(acs_rs_kwh - arr_rs_kwh, 2)

    @staticmethod
    def energy_availability_pct(energy_supplied_mu: float, energy_requirement_mu: float) -> float:
        if energy_requirement_mu == 0:
            return 0.0
        return round(energy_supplied_mu / energy_requirement_mu * 100, 2)

    # -- KPI: Industrial Tariffs (by state) ----------------------

    _TARIFF_COLS = {
        "National avg": "national_avg_rs_kwh",
        "Maharashtra": "maharashtra_rs_kwh",
        "Gujarat": "gujarat_rs_kwh",
        "Tamil Nadu": "tamil_nadu_rs_kwh",
        "Uttar Pradesh": "uttar_pradesh_rs_kwh",
    }

    def _compute_industrial_tariffs(self, spec):
        ds = self.dataset("industrial_tariffs")
        fy = self._fy_points(ds)
        points, audit = [], []
        for year in FY_YEARS:
            dp = fy.get(year)
            if dp is None:
                points.append(SeriesPoint(year, fy_label(year)))
                continue
            breakdown = {}
            for label, col in self._TARIFF_COLS.items():
                v = dp.get(col)
                if v is not None:
                    breakdown[label] = v
            headline = dp.get("national_avg_rs_kwh")
            audit.append(
                AuditEntry(
                    period=dp.period,
                    formula="average billing rate for HT/LT industrial consumers, ₹/kWh (national + major states); reported directly",
                    inputs={label: dp.get(col) for label, col in self._TARIFF_COLS.items()},
                    output=headline,
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
                    value=headline,
                    breakdown=breakdown or None,
                    target_value=spec.target_value,
                    revision=dp.revision,
                )
            )
        return points, audit, self._collect_unresolved(spec, fy), self._current_from(points, fy)

    # -- KPI: Discom AT&C Losses & Financial Health -------------

    def _compute_discom_financial_health(self, spec):
        ds = self.dataset("discom")
        fy = self._fy_points(ds)
        points, audit = [], []
        for year in FY_YEARS:
            dp = fy.get(year)
            if dp is None:
                points.append(SeriesPoint(year, fy_label(year)))
                continue
            atc = dp.get("atc_loss_pct")
            ei, er = dp.get("energy_input_mu"), dp.get("energy_realised_mu")
            if atc is None and ei and er:
                atc = self.calculate_atc_losses_pct(ei, er)
            gap = dp.get("acs_arr_gap_rs_kwh")
            if gap is None and dp.get("acs_rs_kwh") and dp.get("arr_rs_kwh"):
                gap = self.acs_arr_gap(dp.get("acs_rs_kwh"), dp.get("arr_rs_kwh"))
            audit.append(
                AuditEntry(
                    period=dp.period,
                    formula="AT&C loss % = (Energy Input - Energy Realised) / Energy Input * 100 ; ACS-ARR gap = Avg Cost of Supply - Avg Revenue Realised (₹/kWh)",
                    inputs={
                        "atc_loss_pct": atc,
                        "acs_arr_gap_rs_kwh": gap,
                        "discom_accumulated_losses_rs_000cr": dp.get("discom_accumulated_losses_rs_000cr"),
                        "discom_annual_pl_rs_cr": dp.get("discom_annual_pl_rs_cr"),
                    },
                    output=atc,
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
                    value=atc,
                    secondary_value=gap,
                    target_value=spec.target_value,
                    revision=dp.revision,
                )
            )
        return points, audit, self._collect_unresolved(spec, fy), self._current_from(points, fy)

    # -- KPI: Power Availability --------------------------------

    def _compute_power_availability(self, spec):
        ds = self.dataset("reliability")
        fy = self._fy_points(ds)
        points, audit = [], []
        for year in FY_YEARS:
            dp = fy.get(year)
            if dp is None:
                points.append(SeriesPoint(year, fy_label(year)))
                continue
            avail = dp.get("energy_availability_pct")
            if avail is None and dp.get("energy_not_supplied_pct") is not None:
                avail = round(100 - dp.get("energy_not_supplied_pct"), 2)
            audit.append(
                AuditEntry(
                    period=dp.period,
                    formula="availability % = energy supplied / energy requirement * 100 (= 100 - energy-not-supplied %)",
                    inputs={
                        "energy_availability_pct": dp.get("energy_availability_pct"),
                        "energy_not_supplied_pct": dp.get("energy_not_supplied_pct"),
                        "rural_hrs_supply": dp.get("rural_hrs_supply"),
                        "urban_hrs_supply": dp.get("urban_hrs_supply"),
                    },
                    output=avail,
                    source_doc=dp.source_doc,
                    source_url=dp.source_url,
                    page_ref=dp.page_ref,
                    revision=dp.revision,
                )
            )
            points.append(
                SeriesPoint(year, fy_label(year), value=avail, target_value=spec.target_value, revision=dp.revision)
            )
        return points, audit, self._collect_unresolved(spec, fy), self._current_from(points, fy)


def get_power_connector() -> PowerConnector:
    return PowerConnector()
