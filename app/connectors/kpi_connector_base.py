"""Safeguard/validation layer that sits on top of the existing generic
connectors (csv/excel/pdf/web in app/connectors/*.py + the extraction
pipeline in app/pipeline/). Those already know how to fetch bytes and pull a
raw value out of a document; KPIConnector adds the Phase 2 rigor on top:

  - a data-quality / proxy-status flag, sourced from app.kpi_specifications
  - range validation (sanity checks) before a value is trusted
  - a hook for derived/calculated metrics (e.g. ratios, deflation)
  - an audit trail: every write records source_url, data_version,
    extraction_confidence and the calculation steps that produced the value

Ministry-specific connectors (petroleum_connector.py, agriculture_connector.py,
etc.) subclass this to declare validation ranges and any derived-metric math;
they reuse get_connector()/extract_raw_value()/clean_numeric() for the actual
parsing rather than re-implementing CSV/Excel/PDF handling.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.connectors.registry import get_connector
from app.kpi_specifications import KPISpec, get_kpi_spec
from app.models import KPI, KPIHistory, KPISource
from app.pipeline.extractor import extract_raw_value
from app.pipeline.normalizer import clean_numeric


class ValidationError(ValueError):
    """Raised when an extracted value fails a KPIConnector's sanity check."""


class KPIConnector:
    """Base class for a ministry's Tier-A/B connector. `valid_ranges` maps a
    KPISource's KPI name (or a fuzzy substring of it) to an inclusive
    (min, max) bound used by validate_data as a sanity check — not a
    business-logic assertion, just a guard against obviously-corrupt parses
    (e.g. a percentage of 950%)."""

    ministry_code: str
    valid_ranges: dict[str, tuple[float, float]] = {}

    def __init__(self, kpi_spec: KPISpec | None = None):
        self.spec = kpi_spec
        self.quality_flag = kpi_spec.data_quality if kpi_spec else "MEDIUM"
        self.is_proxy = kpi_spec.proxy_based if kpi_spec else False
        self.caveats = list(kpi_spec.caveats) if kpi_spec else []

    # -- extraction -----------------------------------------------------

    def extract_data(self, source: KPISource) -> tuple[float | None, str]:
        """Fetch + parse + pull the raw value for a KPISource, reusing the
        existing generic connector registry. Returns (value, content_hash)."""
        connector = get_connector(source.source_type)
        fetch_result = connector.fetch(source.location)
        records = connector.parse(fetch_result.raw, source.parse_config or {})
        raw_value = extract_raw_value(records, source.parse_config or {})
        return clean_numeric(raw_value), fetch_result.content_hash

    # -- validation -------------------------------------------------------

    def validate_data(self, kpi_name: str, value: float | None) -> float:
        """Sanity-check a value against this connector's declared ranges.
        Raises ValidationError on an out-of-range or missing value."""
        if value is None:
            raise ValidationError(f"{kpi_name}: no value could be extracted")

        bounds = self.valid_ranges.get(kpi_name)
        if bounds is None:
            for name, rng in self.valid_ranges.items():
                if name.lower() in kpi_name.lower() or kpi_name.lower() in name.lower():
                    bounds = rng
                    break
        if bounds is not None:
            lo, hi = bounds
            if not (lo <= value <= hi):
                raise ValidationError(f"{kpi_name}: value {value} outside expected range [{lo}, {hi}]")
        return value

    # -- derived metrics ----------------------------------------------------

    def calculate_derived_metrics(self, raw_values: dict[str, float]) -> dict[str, float]:
        """Override in subclasses that need to compute a ratio/derived KPI
        from multiple raw inputs (e.g. Tax-to-GDP). Default: pass through."""
        return raw_values

    # -- audit trail ----------------------------------------------------

    def log_calculation(self, formula: str, inputs: dict[str, Any], output: float) -> str:
        """Return a JSON-encoded audit record of how `output` was derived."""
        return json.dumps(
            {
                "formula": formula,
                "inputs": inputs,
                "output": output,
                "logged_at": datetime.now(timezone.utc).isoformat(),
            }
        )

    # -- persistence ----------------------------------------------------

    def store_with_metadata(
        self,
        db: Session,
        kpi: KPI,
        value: float,
        content_hash: str,
        extraction_confidence: int = 80,
        formula: str | None = None,
        calc_inputs: dict[str, Any] | None = None,
    ) -> KPIHistory:
        """Write the value to KPI.current_value and append a fully-audited
        KPIHistory row (source_url, data_version, confidence, formula, and a
        JSON calculation log)."""
        now = datetime.now(timezone.utc)
        source = kpi.source

        if source is not None:
            source.data_quality = self.quality_flag
            source.is_proxy = self.is_proxy
            source.last_hash = content_hash
            source.last_checked_at = now
            source.last_changed_at = now

        kpi.current_value = value
        kpi.updated_at = now

        audit_log = None
        if formula:
            audit_log = self.log_calculation(formula, calc_inputs or {}, value)

        history = KPIHistory(
            kpi_id=kpi.id,
            value=value,
            recorded_at=now,
            source_hash=content_hash,
            source_url=source.location if source else None,
            data_version=source.data_version if source else "Final",
            extraction_confidence=max(0, min(100, extraction_confidence)),
            calculation_formula=formula,
            audit_log=audit_log,
        )
        db.add(history)
        db.commit()
        db.refresh(history)
        return history

    # -- convenience ----------------------------------------------------

    def run(self, db: Session, kpi: KPI) -> KPIHistory:
        """End-to-end: extract -> validate -> store, using the spec looked up
        for this KPI if one wasn't provided at construction time."""
        if kpi.source is None:
            raise ValidationError(f"{kpi.name}: no data source configured")

        if self.spec is None:
            self.spec = get_kpi_spec(self.ministry_code, kpi.name)
            if self.spec is not None:
                self.quality_flag = self.spec.data_quality
                self.is_proxy = self.spec.proxy_based
                self.caveats = list(self.spec.caveats)

        value, content_hash = self.extract_data(kpi.source)
        value = self.validate_data(kpi.name, value)
        return self.store_with_metadata(db, kpi, value, content_hash)
