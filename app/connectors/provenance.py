"""Loader for the curated, provenance-tracked Tier-A data layer (``data/tier_a/``).

Each Tier-A KPI is computed from one or more CSV files under ``data/tier_a/``.
Every row in those files carries the formula inputs for one period **plus** a
fixed set of trailing provenance columns so the number is always traceable:

    revision      Actual | Provisional | Revised | BudgetEstimate | Estimated
    source_doc    human-readable name of the exact document
    source_url    where that document lives
    page_ref      table / page / section within the document
    published_on  YYYY-MM or YYYY-MM-DD the figure was published
    note          free text (methodology, cross-check source, caveats)

This module does *not* know any KPI formulas - it only turns a CSV into a
sorted, de-duplicated list of :class:`DataPoint` objects. The per-ministry
connectors in ``app/connectors/tier_a/`` consume that.
"""

from __future__ import annotations

import csv
import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from app.pipeline.normalizer import clean_numeric

_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
DATA_ROOT = _DATA_DIR / "tier_a"
TIER_B_ROOT = _DATA_DIR / "tier_b"

PROVENANCE_COLUMNS = ("revision", "source_doc", "source_url", "page_ref", "published_on", "note")

# Ordered best → worst so `latest revision wins` de-dup and GAP detection agree.
REVISION_RANK = {
    "Actual": 5,
    "Provisional": 4,
    "Revised": 3,
    "BudgetEstimate": 2,
    "Estimated": 1,
    "": 0,
}

# Anything at or below this rank should be surfaced by check_sources / GAPS.md.
SOFT_REVISIONS = {"Estimated", "BudgetEstimate", ""}


class ProvenanceError(ValueError):
    """Raised when a curated data file is malformed."""


@dataclass(frozen=True)
class DataPoint:
    """One period of one curated dataset."""

    period: str  # "FY2019-20", "2024-07", "ESY2023-24" - connector-defined
    values: dict[str, float | None]
    revision: str
    source_doc: str
    source_url: str
    page_ref: str
    published_on: str
    note: str
    dataset: str = ""  # basename of the file this came from
    row_number: int = 0  # 1-based data row, for GAP reporting

    @property
    def is_soft(self) -> bool:
        """True when this figure still needs confirmation against a primary source:
        an Estimated/BudgetEstimate/blank revision, or a row carrying no data at all."""
        return self.revision in SOFT_REVISIONS or all(v is None for v in self.values.values())

    def get(self, key: str) -> float | None:
        return self.values.get(key)


@dataclass
class Dataset:
    """A loaded curated CSV: its rows plus file-level metadata."""

    name: str
    path: Path
    points: list[DataPoint] = field(default_factory=list)
    value_columns: tuple[str, ...] = ()

    def content_hash(self) -> str:
        return hashlib.sha256(self.path.read_bytes()).hexdigest()

    def by_period(self) -> dict[str, DataPoint]:
        return {p.period: p for p in self.points}

    def latest(self) -> DataPoint | None:
        return self.points[-1] if self.points else None

    def column(self, key: str) -> list[tuple[str, float | None]]:
        return [(p.period, p.get(key)) for p in self.points]

    def soft_points(self) -> list[DataPoint]:
        return [p for p in self.points if p.is_soft]


def _resolve(path: str | Path, root: Path | None = None) -> Path:
    p = Path(path)
    if not p.is_absolute():
        p = (root or DATA_ROOT) / p
    return p


def load_dataset(
    path: str | Path, *, period_column: str = "period", root: Path | None = None
) -> Dataset:
    """Load one curated CSV into a :class:`Dataset`.

    Rows are sorted by period (lexicographically, which is correct for the
    ``FY20xx-yy`` / ``YYYY-MM`` / ``ESYxxxx-yy`` conventions used here). When two
    rows share a period the one with the higher :data:`REVISION_RANK` wins;
    ties keep the later row in file order.
    """
    p = _resolve(path, root)
    if not p.exists():
        raise ProvenanceError(f"curated data file not found: {p}")

    with p.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None:
            raise ProvenanceError(f"{p.name}: empty file / no header")
        header = [h.strip() for h in reader.fieldnames]
        if period_column not in header:
            raise ProvenanceError(f"{p.name}: missing '{period_column}' column")
        missing = [c for c in PROVENANCE_COLUMNS if c not in header]
        if missing:
            raise ProvenanceError(f"{p.name}: missing provenance columns {missing}")

        value_columns = tuple(
            c for c in header if c != period_column and c not in PROVENANCE_COLUMNS
        )

        merged: dict[str, DataPoint] = {}
        for i, raw in enumerate(reader, start=1):
            row = {(k.strip() if k else k): (v.strip() if isinstance(v, str) else v) for k, v in raw.items()}
            period = row.get(period_column, "")
            if not period:
                continue
            values = {c: clean_numeric(row.get(c)) for c in value_columns}
            revision = row.get("revision", "") or ""
            if revision and revision not in REVISION_RANK:
                raise ProvenanceError(
                    f"{p.name} row {i}: unknown revision {revision!r} "
                    f"(expected one of {sorted(k for k in REVISION_RANK if k)})"
                )
            dp = DataPoint(
                period=period,
                values=values,
                revision=revision,
                source_doc=row.get("source_doc", "") or "",
                source_url=row.get("source_url", "") or "",
                page_ref=row.get("page_ref", "") or "",
                published_on=row.get("published_on", "") or "",
                note=row.get("note", "") or "",
                dataset=p.stem,
                row_number=i,
            )
            prev = merged.get(period)
            if prev is None or REVISION_RANK.get(revision, 0) >= REVISION_RANK.get(prev.revision, 0):
                merged[period] = dp

    points = sorted(merged.values(), key=lambda d: d.period)
    return Dataset(name=p.stem, path=p, points=points, value_columns=value_columns)


def load_many(paths: Iterable[str | Path]) -> dict[str, Dataset]:
    return {ds.name: ds for ds in (load_dataset(p) for p in paths)}


def combined_hash(datasets: Iterable[Dataset]) -> str:
    h = hashlib.sha256()
    for ds in sorted(datasets, key=lambda d: d.name):
        h.update(ds.name.encode())
        h.update(ds.content_hash().encode())
    return h.hexdigest()
