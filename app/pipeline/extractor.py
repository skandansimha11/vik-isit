from __future__ import annotations

from difflib import SequenceMatcher
from typing import Any


def _row_label(row: dict[str, Any], key_column: str | int) -> str:
    if isinstance(key_column, int):
        values = list(row.values())
        return str(values[key_column]) if key_column < len(values) else ""
    return str(row.get(key_column, "") or "")


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()


def find_row(
    records: list[dict[str, Any]], key_column: str | int, key_match: str, threshold: float = 0.6
) -> dict[str, Any] | None:
    """Find the row whose key_column matches key_match exactly, falling back
    to fuzzy matching so minor label drift in source documents (e.g. a report
    renaming "Fiscal Deficit" to "Fiscal Deficit (% of GDP, RE)") doesn't
    silently break extraction."""
    best_row, best_score = None, 0.0
    for row in records:
        label = _row_label(row, key_column)
        if not label:
            continue
        if label.strip().lower() == key_match.strip().lower():
            return row
        score = _similarity(label, key_match)
        if score > best_score:
            best_row, best_score = row, score
    return best_row if best_score >= threshold else None


def extract_raw_value(records: list[dict[str, Any]], config: dict[str, Any]) -> Any:
    """Pull the raw (un-normalized) value for a KPI out of parsed records,
    per the KPISource.parse_config. Supports two shapes:
      - single-stat scrape: [{"label": ..., "value": ...}] (web `selector` mode)
      - tabular lookup: row matched by key_column/key_match, cell read from value_column
    """
    if "selector" in config:
        return records[0].get("value") if records else None

    # Pre-shaped records (e.g. from a computed connector): a single row already
    # carrying the value — take it rather than demanding tabular lookup keys.
    if not {"key_column", "value_column", "key_match"} <= set(config):
        if records and isinstance(records[0], dict) and "value" in records[0]:
            return records[0].get("value")
        return None

    key_column = config["key_column"]
    value_column = config["value_column"]
    key_match = config["key_match"]

    row = find_row(records, key_column, key_match)
    if row is None:
        return None

    if isinstance(value_column, int):
        values = list(row.values())
        return values[value_column] if value_column < len(values) else None
    return row.get(value_column)
