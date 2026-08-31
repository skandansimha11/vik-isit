"""One-off / on-demand: strip em dashes from every text value already stored in
the DB. The app also does this automatically on startup (see
app.database.scrub_stored_em_dashes) - this script is just a manual entry point
for running it against an arbitrary DATABASE_URL without a redeploy.

    # local SQLite
    venv/Scripts/python -m scripts.strip_db_em_dashes

    # production Postgres
    DATABASE_URL="<external connection string>" venv/Scripts/python -m scripts.strip_db_em_dashes
"""
from __future__ import annotations

from app.database import scrub_stored_em_dashes

if __name__ == "__main__":
    print(f"Rewrote {scrub_stored_em_dashes()} row(s) with em dashes removed.")
