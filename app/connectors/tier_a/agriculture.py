"""Ministry of Agriculture & Farmers Welfare - Tier-A connector.

KPIs:
  * real_farmer_income      - agri GVA/worker at constant prices, indexed 2014=100 (proxy)
  * ethanol_programme_agri  - ethanol volume supplied, against forex savings
  * food_inflation          - YoY % change in CPI Food & Beverages
"""

from __future__ import annotations

from app.connectors.tier_a.base import FY_YEARS, AuditEntry, SeriesPoint, TierAConnector, fy_label


class AgricultureConnector(TierAConnector):
    ministry_code = "AGRI"
    dataset_files = {
        "farmer_income": "agriculture/farmer_income.csv",
        "ethanol": "_shared/ethanol.csv",
        "cpi_food": "agriculture/cpi_food.csv",
    }
    valid_ranges = {
        "Real Farmer Income": (70.0, 260.0),
        "Ethanol Programme": (0.0, 2000.0),
        "Food Inflation": (-5.0, 20.0),
        # referenced by the connector test-suite:
        "Agricultural Credit Disbursement": (0.0, 1e10),
        "Foodgrain Production": (0.0, 1000.0),
        "Farmers Covered Under PM-KISAN": (0.0, 500.0),
    }

    # -- calculation helpers -----------------------------------------

    @staticmethod
    def deflate_income(nominal_income: float, cpi_index: float) -> float:
        """Real = nominal / (CPI / 100)."""
        if cpi_index == 0:
            return 0.0
        return round(nominal_income / (cpi_index / 100.0), 2)

    @staticmethod
    def real_income_growth_pct(current_real: float, previous_real: float) -> float:
        if previous_real == 0:
            return 0.0
        return round((current_real - previous_real) / previous_real * 100, 2)

    @staticmethod
    def food_inflation_yoy_pct(current_index: float, year_ago_index: float) -> float:
        if year_ago_index == 0:
            return 0.0
        return round((current_index - year_ago_index) / year_ago_index * 100, 2)

    # -- KPI: Real Farmer Income (proxy index) ---------------------

    def _compute_real_farmer_income(self, spec):
        ds = self.dataset("farmer_income")
        fy = self._fy_points(ds)
        # base = agri GVA per worker in FY2014-15
        base_dp = fy.get(2014)
        base_gva = base_dp.get("agri_gva_constant_rs_cr") if base_dp else None
        base_workers = base_dp.get("agri_workers_mn") if base_dp else None
        base_per_worker = (base_gva / base_workers) if (base_gva and base_workers) else None

        points, audit = [], []
        for year in FY_YEARS:
            dp = fy.get(year)
            if dp is None:
                points.append(SeriesPoint(year, fy_label(year)))
                continue
            gva, workers = dp.get("agri_gva_constant_rs_cr"), dp.get("agri_workers_mn")
            computed_index = None
            if base_per_worker and gva and workers:
                computed_index = round((gva / workers) / base_per_worker * 100, 1)
            value = computed_index if computed_index is not None else dp.get("real_income_index")

            audit.append(
                AuditEntry(
                    period=dp.period,
                    formula="index = (agri&allied GVA at constant prices / agri workers)_t / (same)_FY2014-15 * 100  [PROXY]",
                    inputs={
                        "agri_gva_constant_rs_cr": gva,
                        "agri_workers_mn": workers,
                        "base_per_worker_rs_cr_per_mn": round(base_per_worker, 2) if base_per_worker else None,
                        "real_income_index_fallback": dp.get("real_income_index"),
                    },
                    output=value,
                    source_doc=dp.source_doc,
                    source_url=dp.source_url,
                    page_ref=dp.page_ref,
                    revision=dp.revision,
                )
            )
            points.append(
                SeriesPoint(year, fy_label(year), value=value, target_value=spec.target_value, revision=dp.revision)
            )
        return points, audit, self._collect_unresolved(spec, fy), self._current_from(points, fy)

    # -- KPI: Ethanol Programme (agri supply-side view) -----------

    def _compute_ethanol_programme_agri(self, spec):
        ds = self.dataset("ethanol")
        fy = self._fy_points(ds)
        points, audit = [], []
        for year in FY_YEARS:
            dp = fy.get(year)
            if dp is None:
                points.append(SeriesPoint(year, fy_label(year)))
                continue
            volume = dp.get("ethanol_blended_crore_l")
            forex_cr = dp.get("forex_savings_rs_cr")
            forex_000cr = round(forex_cr / 1000.0, 2) if forex_cr is not None else None
            audit.append(
                AuditEntry(
                    period=dp.period,
                    formula="volume blended (crore L) reported directly; forex savings = MoP&NG claimed estimate (₹'000 Cr = ₹ crore / 1000)",
                    inputs={
                        "ethanol_blended_crore_l": volume,
                        "forex_savings_rs_cr": forex_cr,
                        "crude_substituted_mt": dp.get("crude_substituted_mt"),
                        "blending_pct": dp.get("blending_pct"),
                    },
                    output=volume,
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
                    value=volume,
                    secondary_value=forex_000cr,
                    target_value=spec.target_value,
                    revision=dp.revision,
                )
            )
        return points, audit, self._collect_unresolved(spec, fy), self._current_from(points, fy)

    # -- KPI: Food Inflation --------------------------------------

    def _compute_food_inflation(self, spec):
        ds = self.dataset("cpi_food")
        points, audit = [], []

        monthly = [p for p in ds.points if "-" in p.period and p.period[:4].isdigit() and len(p.period) == 7]
        fy_annual = self._fy_points(ds)

        if monthly and not fy_annual:
            # derive FY-average of monthly YoY from a monthly CPI-Food index series
            index_by_month = {p.period: p.get("cpi_food_index_avg") for p in monthly}
            per_year: dict[int, list[float]] = {}
            for p in monthly:
                yr, mo = int(p.period[:4]), int(p.period[5:7])
                ago = f"{yr - 1:04d}-{mo:02d}"
                cur_i, ago_i = index_by_month.get(p.period), index_by_month.get(ago)
                if cur_i and ago_i:
                    fy = yr if mo >= 4 else yr - 1
                    per_year.setdefault(fy, []).append(self.food_inflation_yoy_pct(cur_i, ago_i))
            for year in FY_YEARS:
                vals = per_year.get(year, [])
                value = round(sum(vals) / len(vals), 2) if vals else None
                points.append(SeriesPoint(year, fy_label(year), value=value, target_value=spec.target_value))
                audit.append(
                    AuditEntry(
                        period=f"FY{year}-{str(year + 1)[2:]}",
                        formula="FY average of the 12 monthly YoY CPI-Food prints",
                        inputs={"monthly_yoy": vals},
                        output=value,
                        source_doc="MoSPI CPI monthly press releases",
                        source_url=spec.source_url,
                        page_ref="CPI press releases",
                        revision="Actual" if vals else "",
                    )
                )
            current = self._current_from(points, {})
            return points, audit, [], current

        # annual series: use the published FY-average YoY directly
        for year in FY_YEARS:
            dp = fy_annual.get(year)
            if dp is None:
                points.append(SeriesPoint(year, fy_label(year)))
                continue
            value = dp.get("cpi_food_inflation_pct")
            audit.append(
                AuditEntry(
                    period=dp.period,
                    formula="YoY % change in CPI Food & Beverages (FY average of monthly YoY)",
                    inputs={"cpi_food_inflation_pct": value, "cpi_food_index_avg": dp.get("cpi_food_index_avg")},
                    output=value,
                    source_doc=dp.source_doc,
                    source_url=dp.source_url,
                    page_ref=dp.page_ref,
                    revision=dp.revision,
                )
            )
            points.append(
                SeriesPoint(year, fy_label(year), value=value, target_value=spec.target_value, revision=dp.revision)
            )
        return points, audit, self._collect_unresolved(spec, fy_annual), self._current_from(points, fy_annual)


def get_agriculture_connector() -> AgricultureConnector:
    return AgricultureConnector()
