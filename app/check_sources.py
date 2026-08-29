"""Tell me what Tier-A data needs refreshing.

    python -m app.check_sources           # report only (offline-tolerant)
    python -m app.check_sources --fetch    # + run best-effort auto-fetchers

For each of the 15 Tier-A KPIs it reports:
  * the latest fiscal year present in the curated CSV(s)
  * the latest fiscal year we'd expect by now, given the source's cadence
  * whether the source URL is reachable and whether it changed since last check
  * an ACTION recommendation

State (URL fingerprints) is cached in ``data/tier_a/.source_state.json`` so
"changed since last check" is meaningful across runs. Network failures never
fail the command — they just show as ``unreachable``.
"""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from app.connectors.provenance import DATA_ROOT, load_dataset
from app.connectors.tier_a import TIER_A_KPIS
from app.connectors.tier_a.base import fy_from_key

STATE_PATH = DATA_ROOT / ".source_state.json"
SOURCES_MD = DATA_ROOT / "SOURCES.md"


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


def _has_soft_rows(datasets: list[str]) -> bool:
    for rel in datasets:
        try:
            ds = load_dataset(rel)
        except Exception:  # noqa: BLE001
            continue
        if ds.points and ds.points[-1].is_soft:
            return True
    return False


def _latest_fy_in_files(datasets: list[str]) -> int | None:
    best: int | None = None
    for rel in datasets:
        try:
            ds = load_dataset(rel)
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


def _load_state() -> dict:
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}


def _save_state(state: dict) -> None:
    STATE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")


def run(fetch: bool = False, today: date | None = None) -> list[dict]:
    today = today or date.today()
    state = _load_state()
    rows: list[dict] = []

    from app.connectors.tier_a import get_tier_a_connector

    for spec in TIER_A_KPIS:
        conn = get_tier_a_connector(spec.ministry_code)
        files = [conn.dataset_files[k] for k in spec.datasets if k in conn.dataset_files]
        latest = _latest_fy_in_files(files)
        expected = _expected_latest_fy(spec.cadence, today)

        probe = _probe(spec.source_url)
        prev_fp = state.get(spec.key, {}).get("fingerprint")
        changed = bool(prev_fp) and bool(probe.get("fingerprint")) and probe["fingerprint"] != prev_fp
        state.setdefault(spec.key, {})
        if probe.get("fingerprint"):
            state[spec.key]["fingerprint"] = probe["fingerprint"]
        state[spec.key]["last_checked"] = today.isoformat()

        stale = latest is not None and latest < expected
        has_soft = _has_soft_rows(files)
        if latest is None:
            action = "NO DATA — populate the curated CSV"
        elif stale and probe["ok"]:
            action = f"UPDATE — data ends FY{latest}-{str(latest+1)[2:]}, expect FY{expected}-{str(expected+1)[2:]}; source reachable"
        elif stale:
            action = f"UPDATE — data ends FY{latest}-{str(latest+1)[2:]}, expect FY{expected}-{str(expected+1)[2:]} (source unreachable now)"
        elif has_soft:
            action = "confirm — latest rows are Estimated/BudgetEstimate (see GAPS.md)"
        elif changed:
            action = "note — source page changed since last check"
        else:
            action = "ok"

        rows.append(
            {
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
            }
        )

    _save_state(state)
    _write_sources_md(rows)

    if fetch:
        _run_fetchers(rows)

    return rows


def _write_sources_md(rows: list[dict]) -> None:
    lines = [
        "# Tier-A data sources & freshness",
        "",
        "Generated by `python -m app.check_sources`. Update the curated CSVs under",
        "`data/tier_a/` from the cited source, then run `python -m app.tier_a_pipeline`.",
        "",
        "| ministry | KPI | data through | expect | source reachable | action |",
        "|---|---|---|---|---|---|",
    ]
    for r in rows:
        dt = f"FY{r['data_through_fy']}-{str(r['data_through_fy']+1)[2:]}" if r["data_through_fy"] else "—"
        ex = f"FY{r['expected_fy']}-{str(r['expected_fy']+1)[2:]}"
        reach = "yes" if r["source_reachable"] else f"no ({r['source_status'] or 'err'})"
        lines.append(f"| {r['ministry']} | {r['kpi']} | {dt} | {ex} | {reach} | {r['action']} |")
    lines += ["", "## Source URLs", ""]
    for spec in TIER_A_KPIS:
        lines.append(f"- **{spec.ministry_code} · {spec.name}** — {spec.source_name}  \n  {spec.source_url} ({spec.cadence})")
    SOURCES_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _run_fetchers(rows: list[dict]) -> None:
    """Best-effort auto-fetchers. Import lazily; any failure is logged, not raised."""
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
                print(f"  fetch[{name}]: FAILED — {exc} (curated data left unchanged)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Check Tier-A data freshness vs. the official sources.")
    parser.add_argument("--fetch", action="store_true", help="also run best-effort auto-fetchers")
    args = parser.parse_args()

    rows = run(fetch=args.fetch)
    print(f"\nTier-A source check ({date.today().isoformat()}):\n")
    print(f"  {'ministry':<7} {'KPI':<26} {'through':<10} {'expect':<10} {'reach':<7} action")
    for r in rows:
        dt = f"FY{r['data_through_fy']}-{str(r['data_through_fy']+1)[2:]}" if r["data_through_fy"] else "—"
        ex = f"FY{r['expected_fy']}-{str(r['expected_fy']+1)[2:]}"
        reach = "yes" if r["source_reachable"] else "NO"
        print(f"  {r['ministry']:<7} {r['kpi']:<26} {dt:<10} {ex:<10} {reach:<7} {r['action']}")
    need = sum(1 for r in rows if r["action"] != "ok")
    print(f"\n{need} of {len(rows)} KPI source(s) need attention. See {SOURCES_MD.relative_to(Path.cwd())}.")


if __name__ == "__main__":
    main()
