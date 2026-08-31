"""Tell me what curated KPI data needs refreshing - all 30 KPIs, both tiers.

    python -m app.check_sources           # report only (offline-tolerant)
    python -m app.check_sources --fetch    # + run Tier-A's best-effort auto-fetchers
    python -m app.check_sources --tier a   # just the 15 Tier-A KPIs
    python -m app.check_sources --tier b   # just the 15 Tier-B KPIs

For each KPI it reports:
  * the latest fiscal year present in the curated CSV(s)
  * the latest fiscal year we'd expect by now, given the source's cadence
  * whether the source URL is reachable and whether it changed since last check
  * an ACTION recommendation

State (URL fingerprints) is cached per tier in ``data/tier_a/.source_state.json``
/ ``data/tier_b/.source_state.json`` so "changed since last check" is
meaningful across runs. Network failures never fail the command - they just
show as ``unreachable``.

Exit code is non-zero when at least one KPI needs attention, so this can gate
a CI job (e.g. fail/annotate a scheduled GitHub Actions run) without extra
plumbing.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from app.connectors.provenance import DATA_ROOT, TIER_B_ROOT, load_dataset
from app.connectors.tier_a import TIER_A_KPIS
from app.connectors.tier_a.base import fy_from_key
from app.connectors.tier_b import TIER_B_KPIS

TIERS = {
    "a": {
        "label": "Tier-A",
        "kpis": TIER_A_KPIS,
        "root": DATA_ROOT,
        "sources_md": DATA_ROOT / "SOURCES.md",
        "state_path": DATA_ROOT / ".source_state.json",
        "get_connector": None,  # set below (avoids import cycles at module load)
    },
    "b": {
        "label": "Tier-B",
        "kpis": TIER_B_KPIS,
        "root": TIER_B_ROOT,
        "sources_md": TIER_B_ROOT / "SOURCES.md",
        "state_path": TIER_B_ROOT / ".source_state.json",
        "get_connector": None,
    },
}


def _current_fy(today: date) -> int:
    """The fiscal year (start year) currently in progress. India FY = Apr-Mar."""
    return today.year if today.month >= 4 else today.year - 1


def _expected_latest_fy(cadence: str, today: date) -> int:
    """Latest FY whose data we'd reasonably expect to be published by now."""
    cur = _current_fy(today)
    c = cadence.lower()
    if "month" in c:
        # monthly sources: current FY has partial data; last complete FY is cur-1
        return cur - 1 if today.month < 7 else cur - 1  # be conservative: prior FY complete
    # annual sources: prior FY's provisional/actual typically out by the following winter
    return cur - 2 if today.month < 4 else cur - 1


def _has_soft_rows(datasets: list[str], root: Path) -> bool:
    for rel in datasets:
        try:
            ds = load_dataset(rel, root=root)
        except Exception:  # noqa: BLE001
            continue
        if ds.points and ds.points[-1].is_soft:
            return True
    return False


def _latest_fy_in_files(datasets: list[str], root: Path) -> int | None:
    best: int | None = None
    for rel in datasets:
        try:
            ds = load_dataset(rel, root=root)
        except Exception:  # noqa: BLE001
            continue
        for p in ds.points:
            y = fy_from_key(p.period)
            if y is not None and (best is None or y > best):
                best = y
    return best


def _probe(url: str) -> dict:
    try:
        import requests

        resp = requests.get(
            url, timeout=10, headers={"User-Agent": "MinistryDashboardBot/1.0"}, allow_redirects=True
        )
        fp = resp.headers.get("ETag") or resp.headers.get("Last-Modified") or str(len(resp.content))
        return {"ok": resp.status_code < 400, "status": resp.status_code, "fingerprint": fp}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "status": None, "fingerprint": None, "error": str(exc)[:80]}


def _load_state(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}


def _save_state(path: Path, state: dict) -> None:
    path.write_text(json.dumps(state, indent=2), encoding="utf-8")


def _connector_getter(tier: str):
    if tier == "a":
        from app.connectors.tier_a import get_tier_a_connector

        return get_tier_a_connector
    from app.connectors.tier_b import get_tier_b_connector

    return get_tier_b_connector


def run_tier(tier: str, today: date | None = None) -> list[dict]:
    """Check every KPI in one tier ('a' or 'b') against its official source."""
    cfg = TIERS[tier]
    today = today or date.today()
    root: Path = cfg["root"]
    state = _load_state(cfg["state_path"])
    get_connector = _connector_getter(tier)
    rows: list[dict] = []

    for spec in cfg["kpis"]:
        conn = get_connector(spec.ministry_code)
        files = [conn.dataset_files[k] for k in spec.datasets if k in conn.dataset_files]
        latest = _latest_fy_in_files(files, root)
        expected = _expected_latest_fy(spec.cadence, today)

        probe = _probe(spec.source_url)
        prev_fp = state.get(spec.key, {}).get("fingerprint")
        changed = bool(prev_fp) and bool(probe.get("fingerprint")) and probe["fingerprint"] != prev_fp
        state.setdefault(spec.key, {})
        if probe.get("fingerprint"):
            state[spec.key]["fingerprint"] = probe["fingerprint"]
        state[spec.key]["last_checked"] = today.isoformat()

        stale = latest is not None and latest < expected
        has_soft = _has_soft_rows(files, root)
        if latest is None:
            action = "NO DATA - populate the curated CSV"
        elif stale and probe["ok"]:
            action = f"UPDATE - data ends FY{latest}-{str(latest+1)[2:]}, expect FY{expected}-{str(expected+1)[2:]}; source reachable"
        elif stale:
            action = f"UPDATE - data ends FY{latest}-{str(latest+1)[2:]}, expect FY{expected}-{str(expected+1)[2:]} (source unreachable now)"
        elif has_soft:
            action = "confirm - latest rows are Estimated/BudgetEstimate (see GAPS.md)"
        elif changed:
            action = "note - source page changed since last check"
        else:
            action = "ok"

        rows.append(
            {
                "tier": cfg["label"],
                "ministry": spec.ministry_code,
                "kpi": spec.name,
                "key": spec.key,
                "data_through_fy": latest,
                "expected_fy": expected,
                "source_reachable": probe["ok"],
                "source_status": probe.get("status"),
                "changed": changed,
                "action": action,
                "source_url": spec.source_url,
                "source_name": spec.source_name,
                "cadence": spec.cadence,
            }
        )

    _save_state(cfg["state_path"], state)
    _write_sources_md(tier, rows)
    return rows


def _write_sources_md(tier: str, rows: list[dict]) -> None:
    cfg = TIERS[tier]
    lines = [
        f"# {cfg['label']} data sources & freshness",
        "",
        f"Generated by `python -m app.check_sources --tier {tier}`. Update the curated CSVs",
        f"under `{cfg['root'].relative_to(Path.cwd()) if cfg['root'].is_relative_to(Path.cwd()) else cfg['root']}/`",
        f"from the cited source, then run `python -m app.tier_{tier}_pipeline`.",
        "",
        "| ministry | KPI | data through | expect | source reachable | action |",
        "|---|---|---|---|---|---|",
    ]
    for r in rows:
        dt = f"FY{r['data_through_fy']}-{str(r['data_through_fy']+1)[2:]}" if r["data_through_fy"] else "-"
        ex = f"FY{r['expected_fy']}-{str(r['expected_fy']+1)[2:]}"
        reach = "yes" if r["source_reachable"] else f"no ({r['source_status'] or 'err'})"
        lines.append(f"| {r['ministry']} | {r['kpi']} | {dt} | {ex} | {reach} | {r['action']} |")
    lines += ["", "## Source URLs", ""]
    for r in rows:
        lines.append(f"- **{r['ministry']} · {r['kpi']}** - {r['source_name']}  \n  {r['source_url']} ({r['cadence']})")
    cfg["sources_md"].write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(fetch: bool = False, tiers: str = "ab", today: date | None = None) -> list[dict]:
    """Run the freshness check across the requested tiers ('a', 'b', or 'ab' for both)."""
    rows: list[dict] = []
    for t in tiers:
        rows.extend(run_tier(t, today=today))

    if fetch and "a" in tiers:
        _run_fetchers(rows)

    return rows


def _run_fetchers(rows: list[dict]) -> None:
    """Best-effort auto-fetchers (Tier-A only - see app.connectors.tier_a.fetchers).
    Import lazily; any failure is logged, not raised."""
    try:
        from app.connectors.tier_a import fetchers
    except Exception as exc:  # noqa: BLE001
        print(f"  (auto-fetchers unavailable: {exc})")
        return
    log_path = DATA_ROOT / ".fetch_log.jsonl"
    with log_path.open("a", encoding="utf-8") as log:
        for name, fn in fetchers.ALL.items():
            try:
                result = fn()
                log.write(json.dumps({"fetcher": name, **result}) + "\n")
                print(f"  fetch[{name}]: {result.get('summary', 'done')}")
            except Exception as exc:  # noqa: BLE001
                log.write(json.dumps({"fetcher": name, "ok": False, "error": str(exc)[:200]}) + "\n")
                print(f"  fetch[{name}]: FAILED - {exc} (curated data left unchanged)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Check curated KPI data freshness vs. the official sources.")
    parser.add_argument("--fetch", action="store_true", help="also run Tier-A's best-effort auto-fetchers")
    parser.add_argument("--tier", choices=["a", "b", "ab"], default="ab", help="which tier(s) to check (default: both)")
    args = parser.parse_args()

    tiers = "ab" if args.tier == "ab" else args.tier
    rows = run(fetch=args.fetch, tiers=tiers)

    print(f"\nCurated-data source check ({date.today().isoformat()}):\n")
    print(f"  {'tier':<7} {'ministry':<9} {'KPI':<26} {'through':<10} {'expect':<10} {'reach':<7} action")
    for r in rows:
        dt = f"FY{r['data_through_fy']}-{str(r['data_through_fy']+1)[2:]}" if r["data_through_fy"] else "-"
        ex = f"FY{r['expected_fy']}-{str(r['expected_fy']+1)[2:]}"
        reach = "yes" if r["source_reachable"] else "NO"
        print(f"  {r['tier']:<7} {r['ministry']:<9} {r['kpi']:<26} {dt:<10} {ex:<10} {reach:<7} {r['action']}")

    need = [r for r in rows if r["action"] != "ok"]
    sources_paths = ", ".join(str(TIERS[t]["sources_md"].relative_to(Path.cwd())) for t in tiers)
    print(f"\n{len(need)} of {len(rows)} KPI source(s) need attention. See {sources_paths}.")

    # Non-zero exit when something needs attention - lets a scheduled CI job
    # flag it (e.g. annotate the run / open an issue) without extra plumbing.
    sys.exit(1 if need else 0)


if __name__ == "__main__":
    main()
