"""Ministry of Petroleum & Natural Gas - Tier-A connector.

KPIs:
  * oil_import_dependence  - net oil imports as % of consumption (PPAC headline)
  * ethanol_blending       - blending %, shown against ethanol volume blended
  * refining_efficiency    - refinery capacity utilisation %, against GRM $/bbl
"""

from __future__ import annotations

from app.connectors.tier_a.base import FY_YEARS, AuditEntry, SeriesPoint, TierAConnector, fy_label


class PetroleumConnector(TierAConnector):
    ministry_code = "PETRO"
    dataset_files = {
        "crude": "petroleum/crude.csv",
        "ethanol": "_shared/ethanol.csv",
        "refining": "petroleum/refining.csv",
    }
    valid_ranges = {
        "Oil Import Dependence": (50.0, 100.0),
        "Ethanol Blending %": (0.0, 30.0),
        "Refining Efficiency": (60.0, 130.0),
        # referenced by the connector test-suite:
        "Crude Oil Production": (0.0, 100.0),
        "Natural Gas Production": (0.0, 100.0),
        "LPG Coverage": (0.0, 100.0),
    }

    # -- calculation helpers -----------------------------------------

    @staticmethod
    def calculate_oil_import_dependence(net_crude_imports_mt: float, total_crude_consumption_mt: float) -> float:
        if total_crude_consumption_mt == 0:
            return 0.0
        return round(net_crude_imports_mt / total_crude_consumption_mt * 100, 2)

    @staticmethod
    def calculate_ethanol_blending_pct(
        ethanol_supplied_million_litres: float, petrol_consumption_million_litres: float
    ) -> float:
        denom = petrol_consumption_million_litres + ethanol_supplied_million_litres
        if denom == 0:
            return 0.0
        return round(ethanol_supplied_million_litres / denom * 100, 2)

    @staticmethod
    def calculate_capacity_utilisation(throughput_mt: float, capacity_mt: float) -> float:
        if capacity_mt == 0:
            return 0.0
        return round(throughput_mt / capacity_mt * 100, 2)

    # -- KPI: Oil Import Dependence ---------------------------------

    def _compute_oil_import_dependence(self, spec):
        ds = self.dataset("crude")
        fy = self._fy_points(ds)
        points, audit = [], []
        for year in FY_YEARS:
            dp = fy.get(year)
            if dp is None:
                points.append(SeriesPoint(year, fy_label(year)))
                continue
            published = dp.get("oil_import_dependence_pct")
            net_oil, cons = dp.get("net_oil_imports_mt"), dp.get("petroleum_consumption_mt")
            computed = self._ratio_pct(net_oil, cons) if (net_oil and cons) else None
            # crude-only cross-check
            dom, netc = dp.get("domestic_crude_production_mt"), dp.get("net_crude_imports_mt")
            crude_basis = (
                self.calculate_oil_import_dependence(netc, (dom or 0) + (netc or 0)) if netc else None
            )
            value = published if published is not None else computed
            audit.append(
                AuditEntry(
                    period=dp.period,
                    formula="net oil imports (crude + products) / petroleum-products consumption * 100 (PPAC import-dependency)",
                    inputs={
                        "oil_import_dependence_pct_published": published,
                        "net_oil_imports_mt": net_oil,
                        "petroleum_consumption_mt": cons,
                        "domestic_crude_production_mt": dom,
                        "net_crude_imports_mt": netc,
                        "crude_basis_dependence_pct": crude_basis,
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

    # -- KPI: Ethanol Blending % -----------------------------------

    def _compute_ethanol_blending(self, spec):
        ds = self.dataset("ethanol")
        fy = self._fy_points(ds)
        points, audit = [], []
        for year in FY_YEARS:
            dp = fy.get(year)
            if dp is None:
                points.append(SeriesPoint(year, fy_label(year)))
                continue
            published = dp.get("blending_pct")
            eth, petrol = dp.get("ethanol_blended_crore_l"), dp.get("petrol_consumed_crore_l")
            computed = self.calculate_ethanol_blending_pct(eth, petrol) if (eth and petrol) else None
            value = published if published is not None else computed
            audit.append(
                AuditEntry(
                    period=dp.period,
                    formula="ethanol blended / total petrol consumption * 100 (Ethanol Supply Year)",
                    inputs={
                        "blending_pct_published": published,
                        "ethanol_blended_crore_l": eth,
                        "petrol_consumed_crore_l": petrol,
                        "computed_pct": computed,
                    },
                    output=value,
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
                    value=value,
                    secondary_value=eth,
                    target_value=spec.target_value,
                    revision=dp.revision,
                )
            )
        return points, audit, self._collect_unresolved(spec, fy), self._current_from(points, fy)

    # -- KPI: Refining Efficiency ---------------------------------

    def _compute_refining_efficiency(self, spec):
        ds = self.dataset("refining")
        fy = self._fy_points(ds)
        points, audit = [], []
        for year in FY_YEARS:
            dp = fy.get(year)
            if dp is None:
                points.append(SeriesPoint(year, fy_label(year)))
                continue
            published = dp.get("capacity_utilisation_pct")
            thru, cap = dp.get("refinery_throughput_mt"), dp.get("refinery_capacity_mt")
            computed = self.calculate_capacity_utilisation(thru, cap) if (thru and cap) else None
            value = published if published is not None else computed
            grm = dp.get("gross_refining_margin_usd_bbl")
            audit.append(
                AuditEntry(
                    period=dp.period,
                    formula="capacity utilisation % = refinery throughput / installed capacity * 100",
                    inputs={
                        "capacity_utilisation_pct_published": published,
                        "refinery_throughput_mt": thru,
                        "refinery_capacity_mt": cap,
                        "gross_refining_margin_usd_bbl": grm,
                        "computed_pct": computed,
                    },
                    output=value,
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
                    value=value,
                    secondary_value=grm,
                    target_value=spec.target_value,
                    revision=dp.revision,
                )
            )
        return points, audit, self._collect_unresolved(spec, fy), self._current_from(points, fy)


def get_petroleum_connector() -> PetroleumConnector:
    return PetroleumConnector()
