"""Phase 2 test suite: KPI specs, analysis frameworks, Tier A connectors,
insight generation safeguards, and the Tarka chatbot.

Live Claude API calls are mocked out (no network, no API key required) so
this suite runs deterministically in CI. Where sample fixture data is used
(tests/sample_data/*.csv) it's read directly with the stdlib csv module to
keep the test independent of the app's own parsing pipeline under test.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from app import analysis_frameworks, kpi_specifications
from app.config import settings
from app.connectors.agriculture_connector import AgricultureConnector
from app.connectors.finance_connector import FinanceConnector
from app.connectors.kpi_connector_base import ValidationError
from app.connectors.petroleum_connector import PetroleumConnector
from app.connectors.power_connector import PowerConnector
from app.connectors.railways_connector import RailwaysConnector

from tests.conftest import make_ministry

SAMPLE_DIR = Path(__file__).parent / "sample_data"


def _read_csv(name: str) -> list[dict]:
    with open(SAMPLE_DIR / name, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


# ---------------------------------------------------------------------------
# 1. Framework / KPI spec loading
# ---------------------------------------------------------------------------


class TestFrameworkLoading:
    def test_all_ten_frameworks_present(self):
        assert len(analysis_frameworks.FRAMEWORKS) == 10
        for code in ("FIN", "PETRO", "AGRI", "RAIL", "POW", "COMM", "DEF", "EDU", "SKILL", "ROAD"):
            assert code in analysis_frameworks.FRAMEWORKS

    def test_framework_shape(self):
        for code, fw in analysis_frameworks.FRAMEWORKS.items():
            assert fw["good_criteria"], code
            assert fw["mediocre_criteria"], code
            assert fw["poor_criteria"], code
            assert fw["caveats"], code

    def test_core_principles_has_seven(self):
        assert len(analysis_frameworks.CORE_ANALYTICAL_PRINCIPLES) == 7

    def test_all_thirty_kpi_specs_present(self):
        assert len(kpi_specifications.ALL_KPI_SPECS) == 30

    def test_every_ministry_has_three_kpis(self):
        for code in analysis_frameworks.FRAMEWORKS:
            specs = kpi_specifications.get_specs_for_ministry(code)
            assert len(specs) == 3, code

    def test_proxy_kpis_have_proxy_caveat(self):
        for spec in kpi_specifications.ALL_KPI_SPECS:
            if spec.proxy_based:
                assert spec.caveats, spec.key

    def test_get_kpi_spec_fuzzy_match(self):
        # A slightly-off KPI name should still resolve via substring fallback.
        spec = kpi_specifications.get_kpi_spec("POW", "Discom Financial Health & AT&C Losses")
        assert spec is not None
        assert spec.key == "discom_financial_health"


# ---------------------------------------------------------------------------
# 2. Tier A connectors
# ---------------------------------------------------------------------------


class TestPetroleumConnector:
    def test_valid_range_accepts_typical_value(self):
        c = PetroleumConnector()
        assert c.validate_data("Crude Oil Production", 30.5) == 30.5

    def test_valid_range_rejects_impossible_value(self):
        c = PetroleumConnector()
        with pytest.raises(ValidationError):
            c.validate_data("Crude Oil Production", 950.0)

    def test_valid_range_rejects_missing_value(self):
        c = PetroleumConnector()
        with pytest.raises(ValidationError):
            c.validate_data("LPG Coverage", None)

    def test_import_dependence_and_blending_from_sample_data(self):
        rows = _read_csv("petroleum_6mo.csv")
        c = PetroleumConnector()
        assert len(rows) == 6
        for row in rows:
            dependence = c.calculate_oil_import_dependence(
                float(row["net_crude_imports_mt"]), float(row["total_crude_consumption_mt"])
            )
            assert 0 <= dependence <= 100
            blending = c.calculate_ethanol_blending_pct(
                float(row["ethanol_supplied_million_litres"]), float(row["petrol_consumption_million_litres"])
            )
            assert 0 <= blending <= 100


class TestAgricultureConnector:
    def test_deflate_income_from_sample_data(self):
        rows = _read_csv("agriculture_2yr.csv")
        annual = [r for r in rows if r["frequency"] == "annual"]
        assert len(annual) == 2
        c = AgricultureConnector()
        real_incomes = [
            c.deflate_income(float(r["nominal_agri_income_index"]), float(r["cpi_rural_index"])) for r in annual
        ]
        growth = c.real_income_growth_pct(real_incomes[1], real_incomes[0])
        assert isinstance(growth, float)

    def test_food_inflation_from_monthly_rows(self):
        rows = _read_csv("agriculture_2yr.csv")
        monthly = [r for r in rows if r["frequency"] == "monthly"]
        assert len(monthly) == 12
        c = AgricultureConnector()
        yoy = c.food_inflation_yoy_pct(float(monthly[-1]["cpi_food_index"]), float(monthly[0]["cpi_food_index"]))
        assert yoy > 0  # sample data trends upward

    def test_out_of_range_credit_disbursement_rejected(self):
        c = AgricultureConnector()
        with pytest.raises(ValidationError):
            c.validate_data("Agricultural Credit Disbursement", -100.0)


class TestFinanceConnector:
    def test_ten_years_of_fiscal_data_loads(self):
        rows = _read_csv("finance_10yr.csv")
        assert len(rows) == 10

    def test_fiscal_deficit_calculation_matches_documented_formula(self):
        rows = _read_csv("finance_10yr.csv")
        c = FinanceConnector()
        for row in rows:
            deficit_pct = c.calculate_fiscal_deficit_pct(
                float(row["total_expenditure_rs_cr"]),
                float(row["revenue_receipts_rs_cr"]),
                float(row["non_debt_capital_receipts_rs_cr"]),
                float(row["nominal_gdp_rs_cr"]),
            )
            c.validate_data("Fiscal Deficit", deficit_pct)  # must not raise

    def test_tax_to_gdp_and_growth(self):
        rows = _read_csv("finance_10yr.csv")
        c = FinanceConnector()
        gtrs = [float(r["gross_tax_revenue_rs_cr"]) for r in rows]
        gdps = [float(r["nominal_gdp_rs_cr"]) for r in rows]
        ratio = c.calculate_tax_to_gdp(gtrs[-1], gdps[-1])
        assert 5.0 <= ratio <= 20.0
        growth = c.calculate_tax_growth_pct(gtrs[-1], gtrs[-2])
        assert isinstance(growth, float)

    def test_estimate_type_distinguishes_actual_vs_budget(self):
        rows = _read_csv("finance_10yr.csv")
        kinds = {r["estimate_type"] for r in rows}
        assert {"Actual", "Revised", "Budget"} <= kinds


class TestRailwaysConnector:
    def test_five_years_of_freight_data_loads(self):
        rows = _read_csv("railways_5yr.csv")
        assert len(rows) == 5

    def test_freight_and_ntkm_growth(self):
        rows = _read_csv("railways_5yr.csv")
        c = RailwaysConnector()
        mt = [float(r["freight_loaded_mt"]) for r in rows]
        ntkm = [float(r["ntkm_billion"]) for r in rows]
        mt_growth = c.freight_growth_pct(mt[-1], mt[-2])
        ntkm_growth = c.ntkm_growth_pct(ntkm[-1], ntkm[-2])
        assert mt_growth > 0  # sample data trends upward
        assert ntkm_growth > 0

    def test_out_of_range_on_time_performance_rejected(self):
        c = RailwaysConnector()
        with pytest.raises(ValidationError):
            c.validate_data("On-Time Performance", 130.0)


class TestPowerConnector:
    def test_five_years_national_and_state_data_loads(self):
        rows = _read_csv("power_atc_5yr.csv")
        assert len(rows) == 15
        states = {r["state"] for r in rows}
        assert states == {"National", "Uttar Pradesh", "Gujarat"}

    def test_atc_losses_within_realistic_band(self):
        rows = _read_csv("power_atc_5yr.csv")
        c = PowerConnector()
        for row in rows:
            loss_pct = c.calculate_atc_losses_pct(
                float(row["energy_input_units_mu"]), float(row["energy_billed_realised_units_mu"])
            )
            c.validate_data("Transmission & Distribution Losses", loss_pct)  # must not raise

    def test_state_level_dispersion_visible(self):
        rows = _read_csv("power_atc_5yr.csv")
        c = PowerConnector()
        latest = [r for r in rows if r["fiscal_year"] == "FY2024-25"]
        losses = {
            r["state"]: c.calculate_atc_losses_pct(
                float(r["energy_input_units_mu"]), float(r["energy_billed_realised_units_mu"])
            )
            for r in latest
        }
        # states shouldn't all report identical loss rates
        assert len(set(losses.values())) > 1


# ---------------------------------------------------------------------------
# 3. Insight generation (mocked Claude) — safeguard enforcement
# ---------------------------------------------------------------------------


class _FakeBlock:
    type = "text"

    def __init__(self, text: str):
        self.text = text


class _FakeResponse:
    def __init__(self, text: str):
        self.content = [_FakeBlock(text)]


class _FakeMessages:
    def __init__(self, payload: dict):
        self._payload = payload

    def create(self, **kwargs):
        return _FakeResponse(json.dumps(self._payload))


class _FakeAnthropicClient:
    def __init__(self, payload: dict, api_key: str = ""):
        self.messages = _FakeMessages(payload)


@pytest.fixture()
def api_key(monkeypatch):
    monkeypatch.setattr(settings, "anthropic_api_key", "test-key")
    yield "test-key"


def _finance_ministry(db_session):
    return make_ministry(
        db_session,
        "FIN",
        "Ministry of Finance",
        [
            {"name": "Fiscal Deficit", "unit": "% of GDP", "current_value": 5.1, "target_value": 4.5, "higher_is_better": False},
            {"name": "Tax Collection Growth", "unit": "% YoY", "current_value": 14.2, "target_value": 12.0},
        ],
    )


def _skill_ministry_with_proxy(db_session):
    # "Job Creation" is proxy_based=True per kpi_specifications (EPFO net-additions proxy).
    return make_ministry(
        db_session,
        "SKILL",
        "Ministry of Skill Development & Entrepreneurship",
        [
            {"name": "Job Creation", "unit": "Lakh formal jobs/yr", "current_value": 78.0, "target_value": 90.0},
            {"name": "Youth NEET Rate", "unit": "%", "current_value": 22.5, "target_value": 20.0, "higher_is_better": False},
        ],
    )


class TestInsightGeneration:
    def test_valid_response_is_accepted_and_cached(self, db_session, api_key, monkeypatch):
        import app.claude_service as cs

        ministry = _finance_ministry(db_session)
        payload = {
            "headline": "Mediocre",
            "time_period_judged": "FY2015-16 to FY2024-25",
            "key_evidence": [
                "Fiscal Deficit at 5.1% of GDP vs a 4.5% target, 88.2% progress.",
                "Tax Collection Growth at 14.2% YoY against a 12.0% target, 118% progress.",
                "Tax buoyancy suggests revenue-led rather than expenditure-led consolidation.",
            ],
            "important_caveats": ["High nominal GDP growth mechanically lowers deficit ratios."],
            "proxy_disclosure": None,
            "comparative_context": "Deficit remains above the pre-COVID 4.5% FRBM glide path target.",
            "forward_implications": "Continued consolidation needed to reach the medium-term anchor.",
            "data_quality_notes": "HIGH",
        }
        monkeypatch.setattr(cs.anthropic, "Anthropic", lambda api_key: _FakeAnthropicClient(payload))

        insight, cached = cs.get_or_generate_insights(db_session, ministry)

        assert cached is False
        assert len(insight.bullets) == 3
        # headline is the deterministic Ministry Performance Score label (app.scoring),
        # not whatever Claude returned — it always wins so the badge never disagrees
        # with the score shown elsewhere in the dashboard.
        assert insight.headline == ministry.score_label
        assert insight.time_period_judged == "FY2015-16 to FY2024-25"
        assert insight.caveats
        assert insight.data_quality_flag == "HIGH"
        assert insight.proxy_disclosure is None

        # second call with unchanged KPI values must hit the cache, not re-call Claude
        insight2, cached2 = cs.get_or_generate_insights(db_session, ministry)
        assert cached2 is True
        assert insight2.id == insight.id

    def test_wrong_evidence_count_is_rejected(self, db_session, api_key, monkeypatch):
        import app.claude_service as cs
        from fastapi import HTTPException

        ministry = _finance_ministry(db_session)
        payload = {
            "headline": "Good",
            "time_period_judged": "FY2024-25",
            "key_evidence": ["only one point"],
            "important_caveats": ["some caveat"],
            "proxy_disclosure": None,
            "comparative_context": "",
            "forward_implications": "",
            "data_quality_notes": "HIGH",
        }
        monkeypatch.setattr(cs.anthropic, "Anthropic", lambda api_key: _FakeAnthropicClient(payload))

        with pytest.raises(HTTPException) as exc:
            cs.get_or_generate_insights(db_session, ministry)
        assert exc.value.status_code == 502

    def test_missing_caveats_is_rejected(self, db_session, api_key, monkeypatch):
        import app.claude_service as cs
        from fastapi import HTTPException

        ministry = _finance_ministry(db_session)
        payload = {
            "headline": "Good",
            "time_period_judged": "FY2024-25",
            "key_evidence": ["a", "b", "c"],
            "important_caveats": [],
            "proxy_disclosure": None,
            "comparative_context": "",
            "forward_implications": "",
            "data_quality_notes": "HIGH",
        }
        monkeypatch.setattr(cs.anthropic, "Anthropic", lambda api_key: _FakeAnthropicClient(payload))

        with pytest.raises(HTTPException):
            cs.get_or_generate_insights(db_session, ministry)

    def test_proxy_disclosure_is_force_filled_when_model_omits_it(self, db_session, api_key, monkeypatch):
        """Safeguard #2: if any cited KPI is proxy-based, proxy_disclosure must
        never end up null in the stored insight, even if the model forgets it."""
        import app.claude_service as cs

        ministry = _skill_ministry_with_proxy(db_session)
        payload = {
            "headline": "Mediocre",
            "time_period_judged": "FY2020-21 to FY2025-26",
            "key_evidence": [
                "Job Creation at 78 Lakh/yr vs a 90 Lakh/yr target.",
                "Youth NEET Rate at 22.5% vs a 20.0% target.",
                "Net EPFO additions trending up but below target pace.",
            ],
            "important_caveats": ["PLFS methodology changed in FY2017-18."],
            "proxy_disclosure": None,  # model forgot to disclose, despite a proxy KPI
            "comparative_context": "",
            "forward_implications": "Sustained formalisation needed.",
            "data_quality_notes": "MEDIUM",
        }
        monkeypatch.setattr(cs.anthropic, "Anthropic", lambda api_key: _FakeAnthropicClient(payload))

        insight, _ = cs.get_or_generate_insights(db_session, ministry)

        assert insight.proxy_disclosure is not None
        assert "proxy" in insight.proxy_disclosure.lower()
        assert "Job Creation" in insight.proxy_disclosure


# ---------------------------------------------------------------------------
# 4. Tarka chatbot
# ---------------------------------------------------------------------------


class TestTarkaChatbot:
    def test_explain_kpi_uses_documented_spec_no_api_call(self, db_session):
        """explain_kpi is pure spec lookup — must work with no API key at all."""
        from app.tarka_chatbot import explain_kpi

        ministry = _finance_ministry(db_session)
        result = explain_kpi("Fiscal Deficit", ministry)

        assert result["headline"] == "Fiscal Deficit"
        assert result["data_quality_flag"] == "HIGH"
        assert result["proxy_disclosure"] is None
        assert result["caveats"]
        assert result["time_period_judged"] == "FY 2014-15 onwards"

    def test_explain_kpi_flags_proxy_status(self, db_session):
        from app.tarka_chatbot import explain_kpi

        ministry = _skill_ministry_with_proxy(db_session)
        result = explain_kpi("Job Creation", ministry)

        assert result["data_quality_flag"] == "MEDIUM"
        assert result["proxy_disclosure"] is not None
        assert "proxy" in result["proxy_disclosure"].lower()

    def test_explain_kpi_unknown_name_degrades_gracefully(self, db_session):
        from app.tarka_chatbot import explain_kpi

        ministry = _finance_ministry(db_session)
        result = explain_kpi("Not A Real KPI Name At All", ministry)
        assert result["data_quality_flag"] == "LOW"
        assert result["caveats"]

    def test_answer_performance_question_not_bare_yes_no(self, db_session, api_key, monkeypatch):
        import app.tarka_chatbot as tarka

        ministry = _finance_ministry(db_session)
        payload = {
            "headline": "Mediocre",
            "evidence": ["Fiscal Deficit at 5.1% vs 4.5% target.", "Tax revenue exceeding target."],
            "caveats": ["GDP revisions affect this ratio retroactively."],
            "comparative_context": "Above the pre-COVID FRBM anchor.",
            "forward_implications": "Needs continued consolidation.",
            "time_period_judged": "FY2015-16 to FY2024-25",
            "data_quality_flag": "HIGH",
            "proxy_disclosure": None,
        }
        monkeypatch.setattr(tarka.anthropic, "Anthropic", lambda api_key: _FakeAnthropicClient(payload))

        result = tarka.answer_performance_question(ministry, "Is Finance performing well?")

        assert result["headline"] not in ("Yes", "No")
        # same deterministic-override contract as the insights engine (see
        # claude_service._call_claude / tarka_chatbot._with_deterministic_headline).
        assert result["headline"] == ministry.score_label
        assert result["time_period_judged"]
        assert result["caveats"]

    def test_compare_ministries(self, db_session, api_key, monkeypatch):
        import app.tarka_chatbot as tarka

        m1 = _finance_ministry(db_session)
        m2 = make_ministry(
            db_session,
            "RAIL",
            "Ministry of Railways",
            [{"name": "Freight Volume Growth", "unit": "% YoY", "current_value": 8.5, "target_value": 9.0}],
        )
        payload = {
            "headline": "Railways ahead on delivery pace",
            "evidence": ["Freight Volume Growth at 94% of target.", "Fiscal Deficit at 88% progress toward target."],
            "caveats": ["Different KPI units make a direct score comparison imperfect."],
            "comparative_context": "",
            "forward_implications": "",
            "time_period_judged": "FY2024-25",
            "data_quality_flag": "HIGH",
            "proxy_disclosure": None,
        }
        monkeypatch.setattr(tarka.anthropic, "Anthropic", lambda api_key: _FakeAnthropicClient(payload))

        result = tarka.compare_ministries(m1, m2, aspect="delivery pace")
        assert result["evidence"]
        assert result["caveats"]

    def test_generate_trend_analysis_states_time_period(self, db_session, api_key, monkeypatch):
        import app.tarka_chatbot as tarka

        ministry = _finance_ministry(db_session)
        payload = {
            "headline": "Mixed",
            "evidence": ["Tax revenue growth appears structural, driven by formalisation.", "Deficit spike in FY2020-21 is cyclical (COVID)."],
            "caveats": ["COVID-year figures are structural outliers."],
            "comparative_context": "",
            "forward_implications": "",
            "time_period_judged": "FY2019-20 to FY2024-25",
            "data_quality_flag": "MEDIUM",
            "proxy_disclosure": None,
        }
        monkeypatch.setattr(tarka.anthropic, "Anthropic", lambda api_key: _FakeAnthropicClient(payload))

        result = tarka.generate_trend_analysis(ministry, time_period="last 5 years")
        assert result["time_period_judged"] == "FY2019-20 to FY2024-25"

    def test_suggest_focus_areas_prefers_tier_a(self, db_session, api_key, monkeypatch):
        import app.tarka_chatbot as tarka

        ministry = _finance_ministry(db_session)
        payload = {
            "headline": "Focus areas",
            "evidence": ["Track Fiscal Deficit closely (Tier A, HIGH quality).", "Track Tax Collection Growth (Tier A, HIGH quality)."],
            "caveats": ["Avoid over-weighting the Tier C tax-harassment proxy."],
            "comparative_context": "",
            "forward_implications": "",
            "time_period_judged": "Going forward from FY2025-26",
            "data_quality_flag": "HIGH",
            "proxy_disclosure": None,
        }
        monkeypatch.setattr(tarka.anthropic, "Anthropic", lambda api_key: _FakeAnthropicClient(payload))

        result = tarka.suggest_focus_areas(ministry)
        assert result["evidence"]

    def test_no_api_key_raises_503(self, db_session, monkeypatch):
        from fastapi import HTTPException

        import app.tarka_chatbot as tarka

        monkeypatch.setattr(settings, "anthropic_api_key", "")
        ministry = _finance_ministry(db_session)
        with pytest.raises(HTTPException) as exc:
            tarka.answer_performance_question(ministry, "Is Finance doing well?")
        assert exc.value.status_code == 503


# ---------------------------------------------------------------------------
# 5. End-to-end: all 5 MVP connectors + insights + 10 Tarka questions
# ---------------------------------------------------------------------------


class TestEndToEnd:
    def test_all_five_tier_a_connectors_run_on_sample_data(self):
        petro = PetroleumConnector()
        agri = AgricultureConnector()
        fin = FinanceConnector()
        rail = RailwaysConnector()
        power = PowerConnector()

        petro_rows = _read_csv("petroleum_6mo.csv")
        for row in petro_rows:
            petro.calculate_oil_import_dependence(
                float(row["net_crude_imports_mt"]), float(row["total_crude_consumption_mt"])
            )

        agri_rows = _read_csv("agriculture_2yr.csv")
        monthly = [r for r in agri_rows if r["frequency"] == "monthly"]
        agri.food_inflation_yoy_pct(float(monthly[-1]["cpi_food_index"]), float(monthly[0]["cpi_food_index"]))

        fin_rows = _read_csv("finance_10yr.csv")
        fin.calculate_tax_to_gdp(
            float(fin_rows[-1]["gross_tax_revenue_rs_cr"]), float(fin_rows[-1]["nominal_gdp_rs_cr"])
        )

        rail_rows = _read_csv("railways_5yr.csv")
        rail.freight_growth_pct(float(rail_rows[-1]["freight_loaded_mt"]), float(rail_rows[-2]["freight_loaded_mt"]))

        power_rows = [r for r in _read_csv("power_atc_5yr.csv") if r["state"] == "National"]
        power.calculate_atc_losses_pct(
            float(power_rows[-1]["energy_input_units_mu"]), float(power_rows[-1]["energy_billed_realised_units_mu"])
        )
        # If we got here without raising, all 5 Tier A connectors ran end-to-end.
        assert True

    def test_tarka_answers_ten_sample_questions(self, db_session, api_key, monkeypatch):
        import app.tarka_chatbot as tarka

        ministry = _finance_ministry(db_session)
        generic_payload = {
            "headline": "Mediocre",
            "evidence": ["a", "b"],
            "caveats": ["a caveat"],
            "comparative_context": "",
            "forward_implications": "",
            "time_period_judged": "FY2024-25",
            "data_quality_flag": "MEDIUM",
            "proxy_disclosure": None,
        }
        monkeypatch.setattr(tarka.anthropic, "Anthropic", lambda api_key: _FakeAnthropicClient(generic_payload))

        questions = [
            "Is Finance performing well?",
            "How has the fiscal deficit trended?",
            "Is tax collection growth structural or cyclical?",
            "What should officials focus on next year?",
            "Is this a good tax administration?",
            "How does this compare to the historical target?",
            "What are the biggest risks?",
            "Explain the fiscal deficit KPI.",
            "Is capital expenditure quality being maintained?",
            "Summarize overall performance.",
        ]
        assert len(questions) == 10
        for q in questions:
            result = tarka.answer_performance_question(ministry, q)
            assert result["headline"]
            assert result["caveats"]
