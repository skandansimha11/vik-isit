from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import settings

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}

engine = create_engine(settings.database_url, connect_args=connect_args)
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
    Alembic migration chain, so this is the lightweight substitute — it only
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
