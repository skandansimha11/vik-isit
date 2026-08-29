"""CLI entrypoint for the ministry data connector pipeline.

Examples:
    python -m app.run_sync --load-config --ministry FIN
    python -m app.run_sync --ministry RAIL
    python -m app.run_sync                     # sync every configured KPI source
"""

from __future__ import annotations

import argparse
import sys

from app.connectors.config_loader import load_all_configs
from app.database import Base, SessionLocal, engine
from app.pipeline.sync_service import sync_all, sync_ministry


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync ministry KPI data from configured sources.")
    parser.add_argument("--ministry", help="Ministry code to sync, e.g. FIN or RAIL. Omit to sync all.")
    parser.add_argument(
        "--load-config",
        action="store_true",
        help="(Re)load ministry/KPI/source definitions from app/connectors/ministries/*.yaml before syncing.",
    )
    args = parser.parse_args()

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if args.load_config:
            ministries = load_all_configs(db)
            print(f"Loaded config for {len(ministries)} ministries: {[m.code for m in ministries]}")

        results = sync_ministry(db, args.ministry) if args.ministry else sync_all(db)

        print(f"\nSync results ({len(results)} KPI sources checked):")
        for r in results:
            line = f"  [{r.status.upper():>16}] {r.kpi_name}"
            if r.status == "updated":
                line += f"   {r.old_value} -> {r.new_value}"
            if r.message:
                line += f"   ({r.message})"
            print(line)

        updated = sum(1 for r in results if r.status == "updated")
        errors = sum(1 for r in results if r.status == "error")
        unchanged = len(results) - updated - errors
        print(f"\n{updated} updated, {unchanged} unchanged, {errors} errors.")

        if errors:
            sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
