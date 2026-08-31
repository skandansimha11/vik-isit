"""DEPRECATED - superseded by `python -m app.tier_a_pipeline`.

Wiring the Tier-A KPIs to their data sources, computing the series, and writing
the audited history is all done by the pipeline now. This shim forwards to it so
old runbooks keep working.
"""

from __future__ import annotations


def wire_tier_a_connectors(db=None):  # noqa: ARG001 - signature kept for compatibility
    from app.database import SessionLocal
    from app.tier_a_pipeline import refresh_tier_a

    own = db is None
    db = db or SessionLocal()
    try:
        results = refresh_tier_a(db)
        return sum(r.status == "updated" for r in results), sum(r.status == "error" for r in results)
    finally:
        if own:
            db.close()


if __name__ == "__main__":
    wired, errors = wire_tier_a_connectors()
    print(f"tier_a_pipeline: {wired} updated, {errors} errors")
