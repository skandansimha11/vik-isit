"""Best-effort auto-fetchers for the handful of Tier-A sources that publish
something machine-approachable. Invoked only by ``python -m app.check_sources --fetch``.

Contract for each fetcher ``fn() -> dict``:
  * MUST NOT raise for a network / parse failure — return ``{"ok": False, "summary": ...}``
  * On a confident parse, append/update rows in the relevant ``data/tier_a/*.csv``
    with ``revision = "Provisional"`` (never overwrite ``Actual`` / ``Revised`` rows)
    and return ``{"ok": True, "summary": ..., "wrote": [...]}``
  * Government PDFs change layout frequently — when in doubt, DO NOT write; report
    what was found so a human can update the CSV.

These are a convenience, not the backbone. The curated CSVs remain the source of truth.
"""

from __future__ import annotations

import re


def _get(url: str, timeout: int = 20):
    import requests

    return requests.get(url, timeout=timeout, headers={"User-Agent": "MinistryDashboardBot/1.0"})


def ppac_snapshot() -> dict:
    """Look for the latest 'oil import dependency' % on the PPAC site."""
    try:
        resp = _get("https://ppac.gov.in/")
        if resp.status_code >= 400:
            return {"ok": False, "summary": f"PPAC site returned {resp.status_code}"}
        text = resp.text
        hits = re.findall(r"import\s+dependen\w*[^0-9%]{0,40}(\d{2}\.\d)\s*%", text, re.I)
        if hits:
            return {
                "ok": False,
                "summary": f"PPAC page mentions import-dependency ~{hits[0]}% — confirm the FY and update data/tier_a/petroleum/crude.csv manually",
                "found": hits,
            }
        return {
            "ok": False,
            "summary": "PPAC reachable but the current Snapshot/Ready-Reckoner is a PDF; download it and update crude.csv / refining.csv / ethanol.csv by hand",
        }
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "summary": f"PPAC fetch failed: {exc}"}


def mospi_cpi() -> dict:
    """CPI-Food YoY via data.gov.in if an API key is configured, else advise manual."""
    import os

    key = os.environ.get("DATA_GOV_IN_API_KEY", "")
    if not key:
        return {
            "ok": False,
            "summary": "no DATA_GOV_IN_API_KEY set — update data/tier_a/agriculture/cpi_food.csv from the monthly MoSPI CPI press release",
        }
    try:
        # Resource id for CPI is not stable across catalog revisions; treat any failure as 'manual'.
        url = f"https://api.data.gov.in/resource/CPI?api-key={key}&format=json&limit=1"
        resp = _get(url)
        return {
            "ok": False,
            "summary": f"data.gov.in CPI endpoint responded {resp.status_code}; verify the resource id, then update cpi_food.csv",
        }
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "summary": f"data.gov.in CPI fetch failed: {exc}"}


def pib_rail_freight() -> dict:
    """PIB monthly 'freight loading' releases carry the running FY total in plain text."""
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
