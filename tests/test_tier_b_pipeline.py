"""Tier-B pipeline: curated data loads, connector formulas, series assembly,
validation, refresh idempotency, and the provenance API for the 15 KPIs of
Commerce & Industry, Defence, Education, Skill Development & Labour and Road."""

from __future__ import annotations

import pytest

from app.connectors.provenance import TIER_B_ROOT, load_dataset
from app.connectors.tier_b import TIER_B_KPIS, compute_kpi, get_tier_b_connector
from app.connectors.tier_b.spec import TIER_B_BY_NAME, TIER_B_MINISTRIES


class TestSpec:
    def test_fifteen_kpis_five_ministries(self):
        assert len(TIER_B_KPIS) == 15
        by_ministry: dict[str, int] = {}
        for k in TIER_B_KPIS:
            by_ministry[k.ministry_code] = by_ministry.get(k.ministry_code, 0) + 1
        assert set(by_ministry) == set(TIER_B_MINISTRIES)
        assert all(v == 3 for v in by_ministry.values())

    def test_every_kpi_is_single_series_with_targets(self):
        for k in TIER_B_KPIS:
            assert k.data_shape == "time_line", k.key
            assert k.chart_type in ("line", "bar"), k.key
            assert k.target.official is not None or k.target.aspirational is not None, k.key
            assert k.target.official_label and k.target.aspirational_label, k.key
            assert k.display_title and k.plain_note, k.key

    def test_names_match_kpi_specifications(self):
        from app.kpi_specifications import get_kpi_spec

        for k in TIER_B_KPIS:
            assert get_kpi_spec(k.ministry_code, k.name) is not None, (k.ministry_code, k.name)


class TestCuratedData:
    def test_every_file_loads_with_provenance(self):
        seen = set()
        for spec in TIER_B_KPIS:
            conn = get_tier_b_connector(spec.ministry_code)
            for key in spec.datasets:
                rel = conn.dataset_files[key]
                if rel in seen:
                    continue
                seen.add(rel)
                ds = load_dataset(rel, root=TIER_B_ROOT)
                assert ds.points, rel
                for p in ds.points:
                    assert p.source_doc and p.source_url, f"{rel} {p.period}"


class TestCompute:
    @pytest.mark.parametrize("spec", TIER_B_KPIS, ids=lambda s: s.key)
    def test_each_kpi_computes_in_range(self, spec):
        series = compute_kpi(spec.key)
        lo, hi = spec.valid_range
        vals = [p.value for p in series.points if p.value is not None]
        assert vals, spec.key
        assert all(lo <= v <= hi for v in vals), spec.key
        assert series.current_value is not None
        assert series.audit

    def test_proxy_flags_propagate(self):
        assert compute_kpi("exam_integrity").is_proxy
        assert compute_kpi("industrial_import_dependence").is_proxy
        assert not compute_kpi("highway_construction").is_proxy


@pytest.fixture()
def tier_b_db(db_session):
    from app.models import KPI, Ministry

    for code in TIER_B_MINISTRIES:
        m = Ministry(code=code, name=f"Ministry {code}", description="")
        db_session.add(m)
        db_session.flush()
        for spec in [s for s in TIER_B_KPIS if s.ministry_code == code]:
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
    def test_refresh_all_and_idempotency(self, tier_b_db):
        from app.models import KPIHistory
        from app.tier_b_pipeline import refresh_tier_b

        r1 = refresh_tier_b(tier_b_db, dry_run=False)
        assert len(r1) == 15
        assert all(r.status in ("updated", "unchanged") for r in r1), [
            (r.kpi_key, r.status, r.message) for r in r1
        ]
        hist_after_first = tier_b_db.query(KPIHistory).count()
        assert hist_after_first == 15

        r2 = refresh_tier_b(tier_b_db, dry_run=False)
        assert all(r.status == "unchanged" for r in r2)
        assert tier_b_db.query(KPIHistory).count() == hist_after_first

    def test_source_metadata_and_presentation(self, tier_b_db):
        from app.models import KPI, KPISource, Ministry
        from app.tier_b_pipeline import refresh_tier_b

        refresh_tier_b(tier_b_db, ministry="ROAD")
        m = tier_b_db.query(Ministry).filter_by(code="ROAD").first()
        kpi = tier_b_db.query(KPI).filter_by(ministry_id=m.id, name="Highway Construction").first()
        src = tier_b_db.query(KPISource).filter_by(kpi_id=kpi.id).first()
        assert src.source_type == "tier_b"
        assert src.is_live is True
        assert kpi.display_title == "National Highway Built per Day"
        assert kpi.data_shape == "time_line"
        assert kpi.aspirational_target == 45.0

    def test_provenance_endpoint(self, tier_b_db):
        from fastapi.testclient import TestClient

        from app import main
        from app.database import get_db
        from app.models import KPI, Ministry
        from app.tier_b_pipeline import refresh_tier_b

        refresh_tier_b(tier_b_db, ministry="EDU")
        main.app.dependency_overrides[get_db] = lambda: tier_b_db
        try:
            client = TestClient(main.app)
            m = tier_b_db.query(Ministry).filter_by(code="EDU").first()
            kpi = tier_b_db.query(KPI).filter_by(ministry_id=m.id, name="Learning Outcomes").first()
            body = client.get(f"/kpis/{kpi.id}/provenance").json()
            assert body["is_live"] is True
            assert body["ministry_code"] == "EDU"
            assert body["audit"] and body["datasets"]
            assert body["aspirational_target"] == 60.0
        finally:
            main.app.dependency_overrides.clear()


class TestCheckSources:
    """Mirrors TestCheckSources in test_tier_a_pipeline.py — same tool, Tier-B slice."""

    def test_runs_offline(self, monkeypatch):
        import app.check_sources as cs

        monkeypatch.setattr(cs, "_probe", lambda url: {"ok": False, "status": None, "fingerprint": None})
        rows = cs.run(fetch=False, tiers="b")
        assert len(rows) == 15
        for r in rows:
            assert r["tier"] == "Tier-B"
            assert "action" in r
            assert r["source_reachable"] is False

    def test_flags_stale_data(self, monkeypatch):
        import datetime as _dt

        import app.check_sources as cs

        monkeypatch.setattr(cs, "_probe", lambda url: {"ok": True, "status": 200, "fingerprint": "x"})
        rows = cs.run(fetch=False, tiers="b", today=_dt.date(2030, 6, 1))
        assert any("UPDATE" in r["action"] for r in rows)

    def test_default_covers_both_tiers(self, monkeypatch):
        import app.check_sources as cs

        monkeypatch.setattr(cs, "_probe", lambda url: {"ok": False, "status": None, "fingerprint": None})
        rows = cs.run(fetch=False)  # tiers="ab" by default
        assert len(rows) == 30
        assert {r["tier"] for r in rows} == {"Tier-A", "Tier-B"}
