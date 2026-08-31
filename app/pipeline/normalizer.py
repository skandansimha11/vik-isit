from __future__ import annotations

import re
from typing import Any

_UNIT_WORDS = re.compile(
    r"\b(cr|crore|crores|lakh|lakhs|mn|million|bn|billion|rs\.?|inr)\b", re.IGNORECASE
)
_STRIP_CHARS = re.compile(r"[₹$,%]")
_NUMBER = re.compile(r"-?\d+(\.\d+)?")
_BLANK_VALUES = {"", "N/A", "NA", "-", "-", "NIL", "NONE"}


def clean_numeric(raw: Any) -> float | None:
    """Normalize a raw scraped/parsed cell into a float, handling common
    government-report formatting: currency symbols, thousands separators,
    percent signs, unit words (Cr/Lakh/Mn/Bn), and parenthesized negatives."""
    if raw is None:
        return None
    if isinstance(raw, bool):
        return None
    if isinstance(raw, (int, float)):
        return float(raw)

    text = str(raw).strip()
    if text.upper() in _BLANK_VALUES:
        return None

    negative = text.startswith("(") and text.endswith(")")
    if negative:
        text = text[1:-1]

    text = _STRIP_CHARS.sub("", text)
    text = _UNIT_WORDS.sub("", text)
    text = text.strip()

    match = _NUMBER.search(text)
    if not match:
        return None

    value = float(match.group())
    return -value if negative else value
