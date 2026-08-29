"""Tier-A pipeline: provenance loader, connector formulas, series assembly,
validation, refresh idempotency, source checker, and the provenance API."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from app.connectors.kpi_connector_base import ValidationError
from app.connectors.provenance import DATA_ROOT, ProvenanceError, load_dataset
from app.connectors.tier_a import TIER_A_KPIS, compute_kpi, get_tier_a_connector
from app.connectors.tier_a.spec import TIER_A_BY_NAME, TIER_A_MINISTRIES

FIXTURES = Path(__file__).parent / "fixtures"


# --------------------------------------------------------------------------
# 1. Provenance dataset loader
# --------------------------------------------------------------------------


class TestProvenanceLoader:
    def test_every_curated_file_loads(self):
        seen = set()
        for spec in TIER_A_KPIS:
            conn = get_tier_a_connector(spec.ministry_code)
            for key in spec.datasets:
                rel = conn.dataset_files[key]
                if rel in seen:
                    continue
                seen.add(rel)
                ds = load_dataset(rel)
                assert ds.points, f"{rel} produced no rows"
                # provenance columns present on every point
                for p in ds.points:
                    assert p.source_doc and p.source_url, f"{rel} {p.period}: missing source"

    def test_latest_revision_wins_on_duplicate_period(self, tmp_path):
        f = tmp_path / "dup.csv"
        f.write_text(
            "period,x,revision,source_doc,source_url,page_ref,published_on,note\n"
            "FY2020-21,10,Estimated,d,u,p,2021-01,n\n"
            "FY2020-21,12,Actual,d,u,p,2022-01,n\n",
            encoding="utf-8",
        )
        ds = load_dataset(f)
        assert len(ds.points) == 1
        assert ds.points[0].get("x") == 12.0
        assert ds.points[0].revision == "Actual"

    def test_missing_provenance_columns_rejected(self, tmp_path):
        f = tmp_path / "bad.csv"
        f.write_text("period,x\nFY2020-21,10\n", encoding="utf-8")
        with pytest.raises(ProvenanceError):
            load_dataset(f)

    def test_unknown_revision_rejected(self, tmp_path):
        f = tmp_path / "bad2.csv"
        f.write_text(
            "period,x,revision,source_doc,source_url,page_ref,published_on,note\n"
            "FY2020-21,10,Guess,d,u,p,2021,n\n",
            encoding="utf-8",
        )
        with pytest.raises(ProvenanceError):
            load_dataset(f)

    def test_soft_flag(self):
        ds = load_dataset("finance/fiscal.csv")
        by_period = ds.by_period()
        assert not by_period["FY2018-19"].is_soft  # Actual
        assert by_period["FY2025-26"].is_soft  # BudgetEstimate


# --------------------------------------------------------------------------
# 2. Connector calculation helpers (formulas)
# --------------------------------------------------------------------------


class TestFormulas:
    def test_fiscal_deficit(self):
        c = get_tier_a_connector("FIN")
        # GFD = 40 - (25 + 3) = 12 ; /200 * 100 = 6.0
        assert c.calculate_fiscal_deficit_pct(40, 25, 3, 200) == 6.0

    def test_tax_to_gdp_and_growth(self):
        c = get_tier_a_connector("FIN")
        assert c.calculate_tax_to_gdp(30, 250) == 12.0
        assert c.calculate_tax_growth_pct(110, 100) == 10.0

    def test_oil_import_dependence(self):
        c = get_tier_a_connector("PETRO")
        assert c.calculate_oil_import_dependence(80, 100) == 80.0
        assert c.calculate_oil_import_dependence(5, 0) == 0.0

    def test_ethanol_blending(self):
        c = get_tier_a_connector("PETRO")
        # 10 / (90 + 10) * 100 = 10.0
        assert c.calculate_ethanol_blending_pct(10, 90) == 10.0

    def test_deflate_income(self):
        c = get_tier_a_connector("AGRI")
        assert c.deflate_income(120, 120) == 100.0
        assert c.food_inflation_yoy_pct(110, 100) == 10.0

    def test_freight_growth(self):
        c = get_tier_a_connector("RAIL")
        assert c.freight_growth_pct(105, 100) == 5.0
        assert c.ntkm_growth_pct(0, 100) is not None

    def test_atc_losses(self):
        c = get_tier_a_connector("POW")
        # (100 - 82) / 100 * 100 = 18.0
        assert c.calculate_atc_losses_pct(100, 82) == 18.0

    def test_validation_ranges(self):
        petro = get_tier_a_connector("PETRO")
        assert petro.validate_data("Oil Import Dependence", 85.0) == 85.0
        with pytest.raises(ValidationError):
            petro.validate_data("Oil Import Dependence", 250.0)
        with pytest.raises(ValidationError):
            petro.validate_data("Crude Oil Production", None)


# --------------------------------------------------------------------------
# 3. Series assembly for all 15 KPIs
# --------------------------------------------------------------------------


class TestSeriesAssembly:
    @pytest.mark.parametrize("spec", TIER_A_KPIS, ids=lambda s: s.key)
    def test_compute_produces_valid_series(self, spec):
        s = compute_kpi(spec.key)
        assert s.kpi_name == spec.name
        assert s.data_shape == spec.data_shape
        assert len(s.points) == 12  # FY2014-15 .. FY2025-26
        assert s.points[0].year == 2014 and s.points[-1].year == 2025

        lo, hi = spec.valid_range
        for p in s.points:
            if p.value is not None:
                assert lo <= p.value <= hi, f"{spec.key} {p.period_label}={p.value} out of range"
            if spec.data_shape == "time_breakdown" and p.breakdown:
                assert all(isinstance(v, (int, float)) for v in p.breakdown.values())
            if spec.data_shape == "time_dual":
                # at least the later points should carry a secondary value
                pass
        assert s.current_value is not None
        assert s.source_name and s.source_url
        assert s.audit, "audit trail is empty"

    def test_charts_are_kept_simple(self):
        # after the layman-friendliness pass, every Tier-A chart is a single
        # primary series (line) or a small stacked/multi-line breakdown — no dual axes.
        for spec in TIER_A_KPIS:
            assert spec.data_shape in ("time_line", "time_breakdown"), spec.key
            assert spec.chart_type in ("line", "stacked_area"), spec.key

    def test_secondary_metrics_still_computed_for_the_table(self):
        # the secondary metric is demoted to the table, not dropped
        for key in ("tax_collection_growth", "ethanol_blending", "refining_efficiency", "train_speeds_capacity"):
            s = compute_kpi(key)
            assert s.secondary_label
            assert any(p.secondary_value is not None for p in s.points), key

    def test_breakdown_kpis_have_breakdowns(self):
        for spec in TIER_A_KPIS:
            if spec.data_shape != "time_breakdown":
                continue
            s = compute_kpi(spec.key)
            assert any(p.breakdown for p in s.points), spec.key

    def test_every_kpi_has_plain_framing_and_targets(self):
        for spec in TIER_A_KPIS:
            s = compute_kpi(spec.key)
            assert s.display_title and s.display_title != s.kpi_name, spec.key
            assert len(s.plain_note) > 20, spec.key
            # target may be None for the proxy KPI, but the label is always set
            assert s.benchmark_label and s.aspirational_label, spec.key

    def test_proxy_kpis_flagged(self):
        for key in ("tax_administration_intensity", "real_farmer_income"):
            assert compute_kpi(key).is_proxy


# --------------------------------------------------------------------------
# 4. Full refresh against a real (in-memory) DB
# --------------------------------------------------------------------------


@pytest.fixture()
def tier_a_db(db_session):
    from app.models import KPI, Ministry

    for code in TIER_A_MINISTRIES:
        m = Ministry(code=code, name=f"Ministry {code}", description="")
        db_session.add(m)
        db_session.flush()
        for spec in [s for s in TIER_A_KPIS if s.ministry_code == code]:
            db_session.add(
                KPI(
                    ministry_id=m.id,
                    name=spec.name,
                    category="general",
                    unit=spec.unit,
                    current_value=0.0,
                    target_value=spec.target_value or 0.0,
                    period="FY 2025-26",
                )
            )
    db_session.commit()
    return db_session


class TestRefresh:
    def test_refresh_all_and_idempotency(self, tier_a_db):
        from app.models import KPIHistory
        from app.tier_a_pipeline import refresh_tier_a

        r1 = refresh_tier_a(tier_a_db, dry_run=False)
        assert len(r1) == 15
        assert all(x.status in ("updated", "unchanged") for x in r1), [
            (x.kpi_name, x.status, x.message) for x in r1
        ]
        assert sum(x.status == "updated" for x in r1) == 15
        hist_after_first = tier_a_db.query(KPIHistory).count()
        assert hist_after_first == 15

        r2 = refresh_tier_a(tier_a_db, dry_run=False)
        assert all(x.status == "unchanged" for x in r2)
        assert tier_a_db.query(KPIHistory).count() == hist_after_first  # no new rows

    def test_source_metadata_written(self, tier_a_db):
        from app.models import KPI, KPISource, Ministry
        from app.tier_a_pipeline import refresh_tier_a

        refresh_tier_a(tier_a_db, ministry="FIN")
        m = tier_a_db.query(Ministry).filter_by(code="FIN").first()
        kpi = tier_a_db.query(KPI).filter_by(ministry_id=m.id, name="Fiscal Deficit").first()
        src = tier_a_db.query(KPISource).filter_by(kpi_id=kpi.id).first()
        assert src.source_type == "tier_a"
        assert src.is_live is True
        assert src.data_quality == "HIGH"
        assert src.source_url and src.source_name
        assert kpi.chart_type == "line" and kpi.data_shape == "time_line"
        assert kpi.display_title == "Government Budget Gap"
        assert kpi.plain_note
        assert kpi.target_value == 4.3 and kpi.aspirational_target == 3.0

    def test_trend_ignores_estimated_tail(self, tier_a_db):
        from app.models import KPI, Ministry
        from app.tier_a_pipeline import refresh_tier_a

        refresh_tier_a(tier_a_db, ministry="POW")
        m = tier_a_db.query(Ministry).filter_by(code="POW").first()
        kpi = tier_a_db.query(KPI).filter_by(ministry_id=m.id, name="Discom Financial Health").first()
        # last two FIRM points: FY23 15.4 -> FY24 16.1 (Actual) => AT&C rising => worsening
        firm = [p for p in sorted(kpi.series, key=lambda p: p.year) if p.revision not in ("Estimated", "BudgetEstimate", "", None)]
        assert firm[-1].value >= firm[-2].value
        assert kpi.trend == "down"  # higher_is_better=False, value rose => worsening

    def test_poisoned_hash_cleared(self, tier_a_db):
        from app.models import KPI, KPISource, Ministry
        from app.tier_a_pipeline import refresh_tier_a

        m = tier_a_db.query(Ministry).filter_by(code="PETRO").first()
        kpi = tier_a_db.query(KPI).filter_by(ministry_id=m.id, name="Oil Import Dependence").first()
        stale = KPISource(
            kpi_id=kpi.id, source_type="ppac", location="ppac:oil:2024", last_hash="POISONED", is_active=True
        )
        tier_a_db.add(stale)
        tier_a_db.commit()

        refresh_tier_a(tier_a_db, ministry="PETRO")
        tier_a_db.refresh(kpi)
        # the tier_a source is now the live one
        assert kpi.source.source_type == "tier_a"
        assert kpi.source.last_hash != "POISONED"

    def test_gaps_file_regenerated(self, tier_a_db):
        from app.tier_a_pipeline import GAPS_PATH, refresh_tier_a

        refresh_tier_a(tier_a_db, dry_run=False)
        assert GAPS_PATH.exists()
        assert "pending confirmation" in GAPS_PATH.read_text(encoding="utf-8")


# --------------------------------------------------------------------------
# 5. Source checker (offline)
# --------------------------------------------------------------------------


class TestCheckSources:
    def test_runs_offline(self, monkeypatch):
        import app.check_sources as cs

        monkeypatch.setattr(cs, "_probe", lambda url: {"ok": False, "status": None, "fingerprint": None})
        rows = cs.run(fetch=False)
        assert len(rows) == 15
        for r in rows:
            assert "action" in r
            assert r["source_reachable"] is False

    def test_flags_stale_data(self, monkeypatch):
        import datetime as _dt

        import app.check_sources as cs

        monkeypatch.setattr(cs, "_probe", lambda url: {"ok": True, "status": 200, "fingerprint": "x"})
        # pretend it's 2030 -> everything is stale
        rows = cs.run(fetch=False, today=_dt.date(2030, 6, 1))
        assert any("UPDATE" in r["action"] for r in rows)


# --------------------------------------------------------------------------
# 6. Provenance API
# --------------------------------------------------------------------------


class TestProvenanceApi:
    def test_endpoint(self, tier_a_db, monkeypatch):
        from fastapi.testclient import TestClient

        from app import main
        from app.database import get_db
        from app.models import KPI, Ministry
        from app.tier_a_pipeline import refresh_tier_a

        refresh_tier_a(tier_a_db, ministry="POW")
        main.app.dependency_overrides[get_db] = lambda: tier_a_db
        try:
            client = TestClient(main.app)
            m = tier_a_db.query(Ministry).filter_by(code="POW").first()
            kpi = tier_a_db.query(KPI).filter_by(ministry_id=m.id, name="Discom Financial Health").first()
            resp = client.get(f"/kpis/{kpi.id}/provenance")
            assert resp.status_code == 200
            body = resp.json()
            assert body["is_live"] is True
            assert body["ministry_code"] == "POW"
            assert body["source_url"]
            assert isinstance(body["audit"], list) and body["audit"]
            assert isinstance(body["caveats"], list)
        finally:
            main.app.dependency_overrides.clear()
