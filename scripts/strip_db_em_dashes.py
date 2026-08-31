"""One-off: strip em dashes from every text value already stored in the DB.

The source constants and AI prompts no longer emit em dashes, but rows seeded
before that change still contain them (KPI plain-notes, ministry descriptions,
cached insight text, ...). This walks every String / Text / JSON column of every
model and rewrites it in place. Idempotent, safe to run repeatedly.

    # local SQLite
    venv/Scripts/python -m scripts.strip_db_em_dashes

    # production Postgres
    DATABASE_URL="<external connection string>" venv/Scripts/python -m scripts.strip_db_em_dashes
"""
from __future__ import annotations

from sqlalchemy import JSON, String, Text, inspect

from app.claude_service import _no_em_dash
from app.database import Base, SessionLocal
# Import models so every table is registered on Base.metadata.
from app import models  # noqa: F401


def _fix(value):
    if isinstance(value, str):
        return _no_em_dash(value)
    if isinstance(value, list):
        return [_fix(v) for v in value]
    if isinstance(value, dict):
        return {k: _fix(v) for k, v in value.items()}
    return value


def main() -> None:
    db = SessionLocal()
    changed = 0
    try:
        for mapper in Base.registry.mappers:
            model = mapper.class_
            cols = [
                c.key
                for c in mapper.columns
                if isinstance(c.type, (String, Text, JSON))
            ]
            if not cols:
                continue
            for row in db.query(model).all():
                touched = False
                for col in cols:
                    old = getattr(row, col)
                    new = _fix(old)
                    if new != old:
                        setattr(row, col, new)
                        touched = True
                if touched:
                    changed += 1
        db.commit()
    finally:
        db.close()
    print(f"Rewrote {changed} row(s) with em dashes removed.")


if __name__ == "__main__":
    main()
