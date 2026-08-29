"""Ministry of Finance — Tier-A connector.

KPIs:
  * fiscal_deficit_pct_gdp   — GFD ÷ Nominal GDP × 100
  * tax_administration_intensity — composite proxy (scrutiny / notices / appeals)
  * tax_collection_growth    — GTR YoY growth %, shown against Tax-to-GDP %
"""

from __future__ import annotations

from app.connectors.tier_a.base import FY_YEARS, AuditEntry, SeriesPoint, TierAConnector, fy_label


class FinanceConnector(TierAConnector):
    ministry_code = "FIN"
    dataset_files = {
        "fiscal": "finance/fiscal.csv",
        "tax_revenue": "finance/tax_revenue.csv",
        "tax_admin": "finance/tax_admin.csv",
    }
    valid_ranges = {
        "Fiscal Deficit": (0.0, 15.0),
        "Tax Collection Growth": (-25.0, 40.0),
        "Tax Harassment Cases": (0.0, 5000.0),
    }

    # -- calculation helpers (also exercised directly by tests) --------

    @staticmethod
    def calculate_fiscal_deficit_pct(
        total_expenditure: float, revenue_receipts: float, non_debt_capital_receipts: float, nominal_gdp: float
    ) -> float:
        gfd = total_expenditure - (revenue_receipts + non_debt_capital_receipts)
        return round(gfd / nominal_gdp * 100, 2)

    @staticmethod
    def calculate_tax_to_gdp(gross_tax_revenue: float, nominal_gdp: float) -> float:
        return round(gross_tax_revenue / nominal_gdp * 100, 2)

    @staticmethod
    def calculate_tax_growth_pct(current: float, previous: float) -> float:
        return round((current - previous) / previous * 100, 2)

    # -- KPI: Fiscal Deficit -----------------------------------------

    def _compute_fiscal_deficit_pct_gdp(self, spec):
        ds = self.dataset("fiscal")
        fy = self._fy_points(ds)
        points: list[SeriesPoint] = []
        audit: list[AuditEntry] = []

        for year in FY_YEARS:
            dp = fy.get(year)
            if dp is None:
                points.append(SeriesPoint(year, fy_label(year)))
                continue
            published = dp.get("gfd_pct_gdp")
            te, rr, ndcr, gdp = (
                dp.get("total_expenditure_rs_cr"),
                dp.get("revenue_receipts_rs_cr"),
                dp.get("non_debt_capital_receipts_rs_cr"),
                dp.get("nominal_gdp_rs_cr"),
            )
            computed = None
            if None not in (te, rr, ndcr, gdp) and gdp:
                computed = self.calculate_fiscal_deficit_pct(te, rr, ndcr, gdp)
            value = published if published is not None else computed
            target = dp.get("target_pct") if dp.get("target_pct") is not None else spec.target_value

            note = ""
            if computed is not None and published is not None and abs(computed - published) > 0.3:
                note = f"formula check: computed {computed} vs published {published} (Δ {round(computed - published, 2)})"
            audit.append(
                AuditEntry(
                    period=dp.period,
                    formula="GFD/GDP*100 ; GFD = TotalExpenditure - (RevenueReceipts + NonDebtCapitalReceipts)",
                    inputs={
                        "gfd_pct_gdp_published": published,
                        "total_expenditure_rs_cr": te,
                        "revenue_receipts_rs_cr": rr,
                        "non_debt_capital_receipts_rs_cr": ndcr,
                        "nominal_gdp_rs_cr": gdp,
                        "computed_pct": computed,
                        "note": note,
                    },
                    output=value,
                    source_doc=dp.source_doc,
                    source_url=dp.source_url,
                    page_ref=dp.page_ref,
                    revision=dp.revision,
                )
            )
            points.append(
                SeriesPoint(year, fy_label(year), value=value, target_value=target, revision=dp.revision)
            )

        current = self._current_from(points, fy)
        return points, audit, self._collect_unresolved(spec, fy), current

    # -- KPI: Tax Collection Growth / Tax-to-GDP --------------------

    def _compute_tax_collection_growth(self, spec):
        ds = self.dataset("tax_revenue")
        fy = self._fy_points(ds)
        points: list[SeriesPoint] = []
        audit: list[AuditEntry] = []

        for year in FY_YEARS:
            dp = fy.get(year)
            prev = fy.get(year - 1)
            if dp is None:
                points.append(SeriesPoint(year, fy_label(year)))
                continue
            gtr = dp.get("gross_tax_revenue_rs_cr")
            gtr_prev = prev.get("gross_tax_revenue_rs_cr") if prev else None
            growth = self.calculate_tax_growth_pct(gtr, gtr_prev) if (gtr and gtr_prev) else None

            t2g = dp.get("gross_tax_to_gdp_pct")
            if t2g is None and gtr and dp.get("nominal_gdp_rs_cr"):
                t2g = self.calculate_tax_to_gdp(gtr, dp.get("nominal_gdp_rs_cr"))

            audit.append(
                AuditEntry(
                    period=dp.period,
                    formula="tax_to_gdp% = GTR_t / NominalGDP_t * 100 (primary) ; growth% = (GTR_t - GTR_{t-1}) / GTR_{t-1} * 100 (context)",
                    inputs={
                        "gross_tax_revenue_rs_cr": gtr,
                        "gross_tax_revenue_prev_rs_cr": gtr_prev,
                        "direct_tax_rs_cr": dp.get("direct_tax_rs_cr"),
                        "indirect_tax_rs_cr": dp.get("indirect_tax_rs_cr"),
                        "gross_tax_to_gdp_pct": t2g,
                        "gross_tax_revenue_growth_pct": growth,
                    },
                    output=t2g,
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
                    value=t2g,
                    secondary_value=growth,
                    target_value=spec.target_value,
                    revision=dp.revision,
                )
            )

        current = self._current_from(points, fy)
        return points, audit, self._collect_unresolved(spec, fy), current

    # -- KPI: Tax Harassment / Administrative Intensity (proxy) ----

    def _compute_tax_administration_intensity(self, spec):
        ds = self.dataset("tax_admin")
        fy = self._fy_points(ds)
        points: list[SeriesPoint] = []
        audit: list[AuditEntry] = []

        for year in FY_YEARS:
            dp = fy.get(year)
            if dp is None:
                points.append(SeriesPoint(year, fy_label(year)))
                continue
            # headline = pending appeals (CIT-A + ITAT + HC) — the citizen-facing backlog
            headline = dp.get("appeals_pending_000")
            scrutiny = dp.get("scrutiny_assessments_000")
            notices = dp.get("notices_143_2_148_000")
            notices_total = round((scrutiny or 0) + (notices or 0), 1) if (scrutiny or notices) else None
            recovery_pct = None
            raised, recovered = dp.get("disputed_demand_raised_rs_cr"), dp.get("disputed_demand_recovered_rs_cr")
            if raised and recovered:
                recovery_pct = round(recovered / raised * 100, 2)

            audit.append(
                AuditEntry(
                    period=dp.period,
                    formula="COMPOSITE PROXY — headline = appeals pending (CIT-A + ITAT + HC); context = scrutiny assessments + 143(2)/148 notices; recovery% = recovered / disputed-demand-raised * 100",
                    inputs={
                        "appeals_pending_000": headline,
                        "scrutiny_assessments_000": scrutiny,
                        "notices_143_2_148_000": notices,
                        "recovery_of_disputed_demand_pct": recovery_pct,
                    },
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
                    secondary_value=notices_total,
                    revision=dp.revision,
                )
            )

        current = self._current_from(points, fy)
        return points, audit, self._collect_unresolved(spec, fy), current


def get_finance_connector() -> FinanceConnector:
    return FinanceConnector()
