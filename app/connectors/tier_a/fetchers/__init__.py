"""Best-effort auto-fetchers for the handful of Tier-A sources that publish
something machine-approachable. Invoked by ``python -m app.auto_sync`` (daily,
via GitHub Actions) and ``python -m app.check_sources --fetch`` (report-only).

Contract for each fetcher ``fn() -> dict``:
  * MUST NOT raise for a network / parse failure - return ``{"ok": False, "summary": ...}``.
  * On a confident, validated parse, return::

        {"ok": True, "summary": "...", "wrote": [{
            "period": "FY2025-26",            # or "ESY2025-26" / "2026-07" - matches the CSV's convention
            "values": {"col_name": 88.4, ...},  # must match the target CSV's existing header exactly
            "source_doc": "...", "source_url": "...", "note": "...",
        }]}

    ``app.auto_sync`` is the only caller that turns ``wrote`` into an actual CSV
    row, and it re-validates independently (schema match, never overwrites a
    firmer-than-Provisional row for the same period) - a fetcher returning
    ``wrote`` is a proposal, not a guarantee it lands.
  * Confidence bar: only set ``ok: True`` when the page states the figure in an
    unambiguous, singular, machine-parseable way. Government PDFs and "at a
    glance" boxes change layout often - a regex that might be matching the
    wrong figure (a different year, a different metric with a similar label)
    must return ``ok: False`` and explain what it saw, so a human decides.

These are a convenience, not the backbone. The curated CSVs remain the source
of truth, and most KPIs here still have no fetcher at all (see
app.auto_sync.FETCHER_FOR_KEY) - their sources are PDFs or dashboards with no
stable, structured access. python -m app.auto_sync writes everything a
fetcher couldn't resolve to data/PENDING_UPDATES.md instead of leaving it to be
rediscovered from scratch.
"""

from __future__ import annotations

import re
from datetime import date


def _get(url: str, timeout: int = 20):
    import requests

    return requests.get(url, timeout=timeout, headers={"User-Agent": "MinistryDashboardBot/1.0"})


def _current_fy_period() -> str:
    today = date.today()
    start = today.year if today.month >= 4 else today.year - 1
    return f"FY{start}-{str(start + 1)[2:]}"


def ppac_snapshot() -> dict:
    """PPAC's homepage occasionally states 'import dependency' as plain text in
    an at-a-glance box (e.g. "crude oil import dependency stood at 88.2% in
    FY25"). When exactly one such figure appears and it's in-range, propose it
    as a Provisional row for the current FY; otherwise just report what's
    there so a human can check the (usually PDF) Snapshot/Ready Reckoner."""
    try:
        resp = _get("https://ppac.gov.in/")
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "summary": f"PPAC fetch failed: {exc}"}
    if resp.status_code >= 400:
        return {"ok": False, "summary": f"PPAC site returned {resp.status_code}"}

    text = resp.text
    hits = re.findall(r"import\s+dependen\w*[^0-9%]{0,40}(\d{2}\.\d)\s*%", text, re.I)
    # de-dupe identical repeated hits (the same box often appears twice in nav + body)
    distinct = sorted(set(hits))
    if len(distinct) == 1:
        value = float(distinct[0])
        if 50.0 <= value <= 100.0:  # mirrors oil_import_dependence's valid_range
            return {
                "ok": True,
                "summary": f"PPAC homepage states import dependency {value}% - proposing it for {_current_fy_period()}",
                "wrote": [{
                    "period": _current_fy_period(),
                    "values": {"oil_import_dependence_pct": value},
                    "source_doc": "PPAC homepage (at-a-glance)",
                    "source_url": "https://ppac.gov.in/",
                    "note": "auto-fetched: single unambiguous match on PPAC homepage, pending confirmation against the Snapshot PDF",
                }],
            }
        return {"ok": False, "summary": f"PPAC homepage value {value}% is outside the expected range - needs a human look"}
    if distinct:
        return {
            "ok": False,
            "summary": f"PPAC homepage mentions import-dependency {len(distinct)} different ways ({distinct}) - ambiguous, confirm manually",
            "found": distinct,
        }
    return {
        "ok": False,
        "summary": "PPAC reachable but the current Snapshot/Ready-Reckoner is a PDF; download it and update crude.csv / refining.csv / ethanol.csv by hand",
    }


def mospi_cpi() -> dict:
    """CPI-Food YoY via data.gov.in's Open Government Data API, when an API key
    is configured. Only writes if the response is well-formed JSON with a
    numeric CPI field for a recognizable month - any surprise in the response
    shape (resource id drift, a schema change) falls back to manual."""
    import os

    key = os.environ.get("DATA_GOV_IN_API_KEY", "")
    if not key:
        return {
            "ok": False,
            "summary": "no DATA_GOV_IN_API_KEY set - update data/tier_a/agriculture/cpi_food.csv from the monthly MoSPI CPI press release",
        }
    resource_id = os.environ.get("DATA_GOV_IN_CPI_RESOURCE_ID", "")
    if not resource_id:
        return {
            "ok": False,
            "summary": "DATA_GOV_IN_API_KEY set but no DATA_GOV_IN_CPI_RESOURCE_ID - look up the current CPI(Food) resource id "
            "on data.gov.in's catalog and set it as a repo/workflow variable, then this fetcher can write automatically",
        }
    try:
        url = f"https://api.data.gov.in/resource/{resource_id}?api-key={key}&format=json&limit=1&sort[month]=desc"
        resp = _get(url)
        if resp.status_code >= 400:
            return {"ok": False, "summary": f"data.gov.in CPI endpoint responded {resp.status_code}; verify the resource id"}
        data = resp.json()
        records = data.get("records") or []
        if not records:
            return {"ok": False, "summary": "data.gov.in CPI endpoint returned no records; verify the resource id"}
        rec = records[0]
        value = rec.get("index") or rec.get("cpi_food") or rec.get("value")
        month = rec.get("month") or rec.get("ref_month")
        if value is None or month is None:
            return {"ok": False, "summary": f"data.gov.in CPI record is missing expected fields: {sorted(rec.keys())}"}
        return {
            "ok": False,  # the exact field names/shape haven't been verified against a live response - report, don't write yet
            "summary": f"data.gov.in CPI endpoint reachable and parseable (month={month}, value={value}) - "
            "verify these are the right fields, then promote this fetcher to write in app/connectors/tier_a/fetchers/__init__.py",
            "found": {"month": month, "value": value},
        }
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "summary": f"data.gov.in CPI fetch failed: {exc}"}


def pib_rail_freight() -> dict:
    """PIB monthly 'freight loading' releases carry the running FY total in
    plain text, but the release URL changes every month with no stable index -
    report reachability so a human can search for the latest release."""
    try:
        resp = _get("https://pib.gov.in/PressReleaseIframePage.aspx?PRID=0")
        return {
            "ok": False,
            "summary": f"PIB reachable ({resp.status_code}); search 'freight loading' for the latest month and update data/tier_a/railways/freight.csv",
        }
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "summary": f"PIB fetch failed: {exc}"}


ALL = {
    "ppac_snapshot": ppac_snapshot,
    "mospi_cpi": mospi_cpi,
    "pib_rail_freight": pib_rail_freight,
}
