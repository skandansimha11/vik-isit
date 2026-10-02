from sqlalchemy import JSON, String, Text, create_engine, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import settings

is_sqlite = settings.database_url.startswith("sqlite")
# connect_timeout=10: a managed Postgres that's gone (expired free instance, host
# down, credentials revoked) should fail in seconds, not hang on the OS TCP timeout
# (which can run 60-130s+) - a hang here previously meant the whole app never
# finished starting, so Render could not route traffic to *any* route, not just
# DB-backed ones. pool_pre_ping catches a connection that went stale mid-session
# (the managed DB recycled it, a network blip) before it causes a confusing
# mid-request error; pool_recycle avoids handing out a connection a proxy/host
# has quietly dropped after sitting idle.
connect_args = {"check_same_thread": False} if is_sqlite else {"connect_timeout": 10}

engine = create_engine(
    settings.database_url,
    connect_args=connect_args,
    pool_pre_ping=True,
    **({} if is_sqlite else {"pool_recycle": 300}),
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def sync_schema() -> None:
    """Best-effort, additive-only schema sync for SQLite: after
    Base.metadata.create_all() has made any brand-new tables, add any model
    columns that are missing from existing tables. This project has no
    Alembic migration chain, so this is the lightweight substitute - it only
    ever runs `ALTER TABLE ... ADD COLUMN`, never drops or alters existing
    columns, and is a no-op on a fully up-to-date DB."""
    if not settings.database_url.startswith("sqlite"):
        return

    inspector = inspect(engine)
    with engine.begin() as conn:
        for table in Base.metadata.sorted_tables:
            if table.name not in inspector.get_table_names():
                continue
            existing_cols = {c["name"] for c in inspector.get_columns(table.name)}
            for column in table.columns:
                if column.name in existing_cols:
                    continue
                col_type = column.type.compile(dialect=engine.dialect)
                default_sql = ""
                if column.default is not None and getattr(column.default, "is_scalar", False):
                    val = column.default.arg
                    if isinstance(val, str):
                        default_sql = f" DEFAULT '{val}'"
                    elif isinstance(val, bool):
                        default_sql = f" DEFAULT {int(val)}"
                    elif isinstance(val, (int, float)):
                        default_sql = f" DEFAULT {val}"
                conn.execute(
                    text(f'ALTER TABLE "{table.name}" ADD COLUMN "{column.name}" {col_type}{default_sql}')
                )


_EM_DASH = "—"


def _strip_em_dash(value):
    if isinstance(value, str):
        return value.replace(f" {_EM_DASH} ", ", ").replace(_EM_DASH, "-")
    if isinstance(value, list):
        return [_strip_em_dash(v) for v in value]
    if isinstance(value, dict):
        return {k: _strip_em_dash(v) for k, v in value.items()}
    return value


def scrub_stored_em_dashes() -> int:
    """Best-effort, idempotent: rewrite any em dash already stored in a text or
    JSON column. The source constants and AI output no longer produce them, but
    rows seeded before that change still contain them (KPI plain-notes, ministry
    descriptions, cached insight text). Runs on startup next to sync_schema();
    a cheap no-op once the data is clean. Never fails the boot."""
    from app import models  # noqa: F401  ensure every table is registered on Base

    changed = 0
    try:
        with SessionLocal() as db:
            for mapper in Base.registry.mappers:
                cols = [c.key for c in mapper.columns if isinstance(c.type, (String, Text, JSON))]
                if not cols:
                    continue
                for row in db.query(mapper.class_).all():
                    touched = False
                    for col in cols:
                        old = getattr(row, col)
                        new = _strip_em_dash(old)
                        if new != old:
                            setattr(row, col, new)
                            touched = True
                    changed += touched
            if changed:
                db.commit()
    except Exception:  # noqa: BLE001 - cosmetic cleanup must never block startup
        return 0
    return changed
