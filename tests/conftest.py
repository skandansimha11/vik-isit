from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
# Import models so they're registered on Base.metadata before create_all.
from app import models  # noqa: F401


@pytest.fixture()
def db_session():
    """An isolated in-memory SQLite DB per test — never touches the real
    ministry_dashboard.db file."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def make_ministry(db_session, code: str, name: str, kpis: list[dict]):
    """Helper: create a Ministry with KPIs (name/category/unit/current/target)."""
    from app.models import KPI, Ministry

    ministry = Ministry(code=code, name=name, description=f"{name} (test fixture)")
    db_session.add(ministry)
    db_session.flush()

    for spec in kpis:
        kpi = KPI(
            ministry_id=ministry.id,
            name=spec["name"],
            category=spec.get("category", "general"),
            unit=spec.get("unit", ""),
            current_value=spec["current_value"],
            target_value=spec["target_value"],
            period=spec.get("period", "FY2025-26"),
            higher_is_better=spec.get("higher_is_better", True),
        )
        db_session.add(kpi)
    db_session.commit()
    db_session.refresh(ministry)
    return ministry
