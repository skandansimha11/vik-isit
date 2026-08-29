"""Base class for the five Tier-B ministry connectors.

Tier-B reuses the entire Tier-A machinery (:class:`TierAConnector`, the
``KPISeries`` / ``SeriesPoint`` / ``AuditEntry`` types, every shared helper).
The only difference is the curated-data root: Tier-B files live under
``data/tier_b/`` instead of ``data/tier_a/``.
"""

from __future__ import annotations

from app.connectors.provenance import TIER_B_ROOT
from app.connectors.tier_a.base import (  # re-export for the ministry modules
    FY_YEARS,
    AuditEntry,
    KPISeries,
    SeriesPoint,
    TierAConnector,
    fy_from_key,
    fy_key,
    fy_label,
)

__all__ = [
    "FY_YEARS",
    "AuditEntry",
    "KPISeries",
    "SeriesPoint",
    "TierBConnector",
    "fy_from_key",
    "fy_key",
    "fy_label",
]


class TierBConnector(TierAConnector):
    """One instance per Tier-B ministry. Identical to :class:`TierAConnector`
    except that datasets resolve against ``data/tier_b/``."""

    data_root = TIER_B_ROOT

    def _simple_series(
        self,
        spec,
        dataset_key: str,
        value_col: str,
        *,
        formula: str,
        secondary_col: str | None = None,
        extra_input_cols: tuple[str, ...] = (),
        target_col: str = "target_value",
    ):
        """The common Tier-B shape: one published headline column per FY, an
        optional secondary column for the data table, and a flat target from the
        spec (or a per-row override in ``target_col``). Returns the standard
        ``(points, audit, unresolved, current)`` tuple."""
        ds = self.dataset(dataset_key)
        fy = self._fy_points(ds)
        points: list[SeriesPoint] = []
        audit: list[AuditEntry] = []

        for year in FY_YEARS:
            dp = fy.get(year)
            if dp is None:
                points.append(SeriesPoint(year, fy_label(year)))
                continue
            value = dp.get(value_col)
            secondary = dp.get(secondary_col) if secondary_col else None
            target = dp.get(target_col)
            if target is None:
                target = spec.target_value

            inputs = {value_col: value}
            if secondary_col:
                inputs[secondary_col] = secondary
            for c in extra_input_cols:
                inputs[c] = dp.get(c)

            audit.append(
                AuditEntry(
                    period=dp.period,
                    formula=formula,
                    inputs=inputs,
                    output=value,
                    source_doc=dp.source_doc,
                    source_url=dp.source_url,
                    page_ref=dp.page_ref,
                    revision=dp.revision,
                )
            )
            points.append(
                SeriesPoint(
                    year,
                    fy_label(year),
                    value=value,
                    secondary_value=secondary,
                    target_value=target,
                    revision=dp.revision,
                )
            )

        return points, audit, self._collect_unresolved(spec, fy), self._current_from(points, fy)
