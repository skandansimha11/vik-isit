"""Base class + result types shared by the five Tier-A ministry connectors.

A connector turns one or more curated :class:`~app.connectors.provenance.Dataset`
objects into a :class:`KPISeries` — the full FY2014-15 → latest analytics series
for one KPI, shaped to match the KPI's ``data_shape`` (see the frontend
``ChartRenderer``), fully validated, with a per-period audit trail.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path

from app.connectors.kpi_connector_base import KPIConnector, ValidationError
from app.connectors.provenance import DATA_ROOT, Dataset, DataPoint, load_dataset
from app.kpi_specifications import get_spec_by_key

# The dashboard's canonical window: FY2014-15 .. FY2025-26 (12 points).
FY_START = 2014
FY_END = 2025
FY_YEARS = list(range(FY_START, FY_END + 1))


def fy_label(year: int) -> str:
    """2014 -> 'FY15' (matches app/seed_dashboard.py and the frontend)."""
    return f"FY{str(year + 1)[2:]}"


def fy_key(year: int) -> str:
    """2014 -> 'FY2014-15' (the `period` convention in the curated FY files)."""
    return f"FY{year}-{str(year + 1)[2:]}"


def fy_from_key(period: str) -> int | None:
    """'FY2019-20' -> 2019 ; 'ESY2019-20' -> 2019 ; tolerant of stray text."""
    import re

    m = re.search(r"(20\d{2})\s*-\s*\d{2}", period)
    return int(m.group(1)) if m else None


@dataclass
class SeriesPoint:
    year: int
    period_label: str
    value: float | None = None
    secondary_value: float | None = None
    target_value: float | None = None
    breakdown: dict[str, float] | None = None
    revision: str | None = None


@dataclass
class AuditEntry:
    period: str
    formula: str
    inputs: dict
    output: float | None
    source_doc: str
    source_url: str
    page_ref: str
    revision: str


@dataclass
class KPISeries:
    kpi_key: str
    kpi_name: str
    display_title: str
    plain_note: str
    ministry_code: str
    points: list[SeriesPoint]
    current_value: float | None
    current_period: str
    current_revision: str
    data_quality: str
    is_proxy: bool
    caveats: list[str]
    source_name: str
    source_url: str
    source_updated_at: str  # published_on of the point behind current_value
    data_shape: str
    chart_type: str
    unit: str
    target_value: float | None
    aspirational_target: float | None
    higher_is_better: bool
    secondary_label: str | None = None
    secondary_unit: str | None = None
    benchmark_label: str | None = None
    aspirational_label: str | None = None
    breakdown_label: str | None = None
    audit: list[AuditEntry] = field(default_factory=list)
    unresolved: list[dict] = field(default_factory=list)  # soft rows -> GAPS.md
    dataset_paths: list[str] = field(default_factory=list)

    @property
    def latest_point(self) -> SeriesPoint | None:
        pts = [p for p in self.points if p.value is not None or p.breakdown]
        return pts[-1] if pts else None


class TierAConnector(KPIConnector):
    """One instance per ministry. Subclasses set ``ministry_code``,
    ``valid_ranges`` and a ``_compute_<kpi_key>`` method per KPI."""

    ministry_code: str = ""
    # dataset basename -> filename under data/tier_a/<ministry>/ (or _shared/)
    dataset_files: dict[str, str] = {}
    # curated-data root; subclassed by the Tier-B connectors (data/tier_b/)
    data_root: Path = DATA_ROOT

    def __init__(self) -> None:
        super().__init__(kpi_spec=None)

    # -- dataset access ------------------------------------------------

    @cached_property
    def _datasets(self) -> dict[str, Dataset]:
        out: dict[str, Dataset] = {}
        for name, rel in self.dataset_files.items():
            out[name] = load_dataset(rel, root=self.data_root)
        return out

    def dataset(self, name: str) -> Dataset:
        if name not in self._datasets:
            raise ValidationError(f"{self.ministry_code}: dataset {name!r} not configured")
        return self._datasets[name]

    def dataset_paths(self, keys: tuple[str, ...] | None = None) -> list[str]:
        names = keys or tuple(self._datasets)
        return [
            str(Path(self._datasets[k].path).relative_to(DATA_ROOT.parent.parent))
            for k in names
            if k in self._datasets
        ]

    # -- entrypoint --------------------------------------------------

    def compute(self, spec) -> KPISeries:
        method = getattr(self, f"_compute_{spec.key}", None)
        if method is None:
            raise ValidationError(f"{self.ministry_code}: no compute method for {spec.key!r}")

        kspec = get_spec_by_key(spec.key)
        caveats = list(kspec.caveats) if kspec else []
        self.quality_flag = spec.data_quality
        self.is_proxy = spec.is_proxy
        self.caveats = caveats

        points, audit, unresolved, current = method(spec)

        # sanity-validate every numeric headline point against the KPI's range
        lo, hi = spec.valid_range
        for p in points:
            if p.value is not None and not (lo <= p.value <= hi):
                raise ValidationError(
                    f"{spec.name} {p.period_label}: value {p.value} outside expected range [{lo}, {hi}]"
                )

        cur_point, cur_period, cur_rev, cur_pub = current
        return KPISeries(
            kpi_key=spec.key,
            kpi_name=spec.name,
            display_title=spec.display_title,
            plain_note=spec.plain_note,
            ministry_code=self.ministry_code,
            points=points,
            current_value=cur_point,
            current_period=cur_period,
            current_revision=cur_rev,
            data_quality=spec.data_quality,
            is_proxy=spec.is_proxy,
            caveats=caveats,
            source_name=spec.source_name,
            source_url=spec.source_url,
            source_updated_at=cur_pub,
            data_shape=spec.data_shape,
            chart_type=spec.chart_type,
            unit=spec.unit,
            target_value=spec.target.official,
            aspirational_target=spec.target.aspirational,
            higher_is_better=spec.higher_is_better,
            secondary_label=spec.secondary_label,
            secondary_unit=spec.secondary_unit,
            benchmark_label=spec.target.official_label,
            aspirational_label=spec.target.aspirational_label,
            breakdown_label=spec.breakdown_label,
            audit=audit,
            unresolved=unresolved,
            dataset_paths=self.dataset_paths(spec.datasets),
        )

    # -- shared helpers -------------------------------------------------

    def _fy_points(self, ds: Dataset) -> dict[int, DataPoint]:
        """Map fiscal-year int -> DataPoint for an FY-keyed dataset."""
        out: dict[int, DataPoint] = {}
        for p in ds.points:
            y = fy_from_key(p.period)
            if y is not None:
                out[y] = p
        return out

    @staticmethod
    def _pct_change(cur: float | None, prev: float | None) -> float | None:
        if cur is None or prev is None or prev == 0:
            return None
        return round((cur - prev) / abs(prev) * 100, 2)

    @staticmethod
    def _ratio_pct(num: float | None, den: float | None) -> float | None:
        if num is None or den is None or den == 0:
            return None
        return round(num / den * 100, 2)

    def _unresolved_row(self, spec, dp: DataPoint, why: str) -> dict:
        return {
            "kpi": spec.name,
            "kpi_key": spec.key,
            "ministry": self.ministry_code,
            "period": dp.period,
            "dataset": dp.dataset,
            "row": dp.row_number,
            "revision": dp.revision or "(blank)",
            "reason": why,
            "source_doc": dp.source_doc,
            "source_url": dp.source_url,
            "page_ref": dp.page_ref,
        }

    def _target_series(self, spec, per_year: dict[int, float] | None = None) -> dict[int, float | None]:
        """Target value for each FY — a flat line at ``spec.target_value`` unless
        the connector supplies a per-year glide path."""
        if per_year:
            return {y: per_year.get(y, spec.target_value) for y in FY_YEARS}
        return {y: spec.target_value for y in FY_YEARS}

    def _current_from(
        self, points: list[SeriesPoint], fy_points: dict[int, DataPoint]
    ) -> tuple[float | None, str, str, str]:
        """Pick the headline (current) value: the latest point that carries a
        firm figure (revision Actual / Provisional / Revised). Falls back to the
        latest point with any data if every trailing point is an estimate.
        Returns (value, period_key, revision, published_on)."""
        from app.connectors.provenance import SOFT_REVISIONS

        with_data = [p for p in points if p.value is not None or p.breakdown]
        if not with_data:
            return (None, "", "", "")
        firm = [p for p in with_data if (p.revision or "") not in SOFT_REVISIONS]
        chosen = firm[-1] if firm else with_data[-1]
        dp = fy_points.get(chosen.year)
        return (
            chosen.value,
            fy_key(chosen.year),
            (dp.revision if dp else (chosen.revision or "")),
            (dp.published_on if dp else ""),
        )

    def _collect_unresolved(self, spec, fy_points: dict[int, DataPoint]) -> list[dict]:
        rows = []
        for year in sorted(fy_points):
            dp = fy_points[year]
            if dp.is_soft:
                blanks = [k for k, v in dp.values.items() if v is None]
                why = f"revision={dp.revision or '(blank)'}"
                if blanks:
                    why += f"; missing columns: {', '.join(blanks)}"
                rows.append(self._unresolved_row(spec, dp, why))
        return rows
