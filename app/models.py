from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Ministry(Base):
    __tablename__ = "ministries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(String(1000), default="")

    kpis: Mapped[list["KPI"]] = relationship(
        back_populates="ministry", cascade="all, delete-orphan"
    )
    insight: Mapped["MinistryInsight | None"] = relationship(
        back_populates="ministry", uselist=False, cascade="all, delete-orphan"
    )

    @property
    def _score_result(self):
        from app.scoring import compute_ministry_score

        return compute_ministry_score(self)

    @property
    def score(self) -> float | None:
        """Composite Ministry Performance Score (0-100). Weighted average of
        this ministry's 2-3 KPI sub-scores per app.scoring.MINISTRY_SCORING:
        weights reflect relative economic importance (never equal by
        default), each sub-score is a direction-aware normalization against
        an aspirational/structural target, a modest trend adjustment nudges
        for a clear multi-year direction, and proxy/low-quality KPIs are
        down-weighted via a data-confidence multiplier rather than dropped."""
        return self._score_result.composite_score

    @property
    def score_label(self) -> str | None:
        """'Strong' | 'Satisfactory' | 'Mediocre' | 'Weak' | 'Poor', per
        app.scoring.SCORE_BANDS."""
        return self._score_result.label

    @property
    def status(self) -> str:
        """'improving' | 'declining' | 'steady', by majority vote across KPI trends."""
        trends = [k.trend for k in self.kpis if k.trend in ("up", "down")]
        if not trends:
            return "steady"
        up = sum(1 for t in trends if t == "up")
        down = len(trends) - up
        if up == down:
            return "steady"
        return "improving" if up > down else "declining"

    @property
    def hero_kpi(self) -> "KPI | None":
        for k in self.kpis:
            if k.hero:
                return k
        return self.kpis[0] if self.kpis else None


class KPI(Base):
    __tablename__ = "kpis"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ministry_id: Mapped[int] = mapped_column(ForeignKey("ministries.id"), nullable=False)

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str] = mapped_column(String(100), default="general")
    unit: Mapped[str] = mapped_column(String(50), default="")

    current_value: Mapped[float] = mapped_column(Float, nullable=False)
    target_value: Mapped[float] = mapped_column(Float, nullable=False)

    period: Mapped[str] = mapped_column(String(50), default="")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )

    # --- Dashboard presentation metadata -----------------------------------
    # chart_type: how the KPI's series should be rendered.
    #   line | dual_axis | grouped_bar | stacked_area | stacked_bar | bar
    chart_type: Mapped[str] = mapped_column(String(30), default="line")
    # data_shape: how KPISeriesPoint rows for this KPI should be read.
    #   time_line | time_dual | time_breakdown | category_compare
    data_shape: Mapped[str] = mapped_column(String(30), default="time_line")
    hero: Mapped[bool] = mapped_column(Boolean, default=False)
    higher_is_better: Mapped[bool] = mapped_column(Boolean, default=True)
    secondary_label: Mapped[str | None] = mapped_column(String(100), nullable=True)
    secondary_unit: Mapped[str | None] = mapped_column(String(50), nullable=True)
    benchmark_label: Mapped[str | None] = mapped_column(String(100), default="Official Target")
    breakdown_label: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Layman-friendly framing + dual targets (populated for Tier-A KPIs)
    display_title: Mapped[str | None] = mapped_column(String(120), nullable=True)
    plain_note: Mapped[str | None] = mapped_column(String(600), nullable=True)
    aspirational_target: Mapped[float | None] = mapped_column(Float, nullable=True)
    aspirational_label: Mapped[str | None] = mapped_column(String(120), nullable=True)

    ministry: Mapped["Ministry"] = relationship(back_populates="kpis")
    source: Mapped["KPISource | None"] = relationship(
        back_populates="kpi", uselist=False, cascade="all, delete-orphan"
    )
    history: Mapped[list["KPIHistory"]] = relationship(
        back_populates="kpi", cascade="all, delete-orphan", order_by="KPIHistory.recorded_at"
    )
    series: Mapped[list["KPISeriesPoint"]] = relationship(
        back_populates="kpi", cascade="all, delete-orphan", order_by="KPISeriesPoint.year"
    )

    def _progress_vs(self, target: float | None) -> float | None:
        """Raw, unclamped progress-to-target %, direction-aware."""
        if not target or self.current_value is None:
            return None
        if self.higher_is_better:
            return (self.current_value / target) * 100
        return (target / self.current_value) * 100 if self.current_value else 0.0

    @property
    def progress_pct(self) -> float | None:
        """How far the KPI has progressed toward its targets, as a %. Blends the
        official / near-term target (weight 0.7) with the aspirational /
        structural target (0.3), so clearing a soft near-term bar doesn't score
        the same as genuine progress toward the real goal. Clamped 0-150."""
        p_official = self._progress_vs(self.target_value)
        if p_official is None:
            return None
        p_aspirational = self._progress_vs(self.aspirational_target)
        blended = p_official if p_aspirational is None else 0.7 * p_official + 0.3 * p_aspirational
        return round(max(0.0, min(blended, 150.0)), 1)

    # Confidence weighting for Ministry.score — shaky data drives the verdict less.
    _QUALITY_WEIGHT = {"HIGH": 1.0, "MEDIUM": 0.9, "LOW": 0.6}

    @property
    def score_weight(self) -> float:
        """Weight this KPI carries in its ministry's score: the headline KPI
        counts double; LOW-quality and proxy KPIs are discounted."""
        w = 2.0 if self.hero else 1.0
        w *= self._QUALITY_WEIGHT.get(self.data_quality, 0.8)
        if self.is_proxy:
            w *= 0.85
        return w

    # --- provenance passthrough (source is 1:1) -------------------------
    @property
    def is_live(self) -> bool:
        return bool(self.source and self.source.is_live)

    @property
    def data_quality(self) -> str | None:
        return self.source.data_quality if self.source else None

    @property
    def is_proxy(self) -> bool:
        return bool(self.source and self.source.is_proxy)

    @property
    def data_version(self) -> str | None:
        return self.source.data_version if self.source else None

    @property
    def source_name(self) -> str | None:
        return self.source.source_name if self.source else None

    @property
    def source_url(self) -> str | None:
        return self.source.source_url if self.source else None

    @property
    def source_cadence(self) -> str | None:
        return self.source.source_cadence if self.source else None

    @property
    def source_updated_at(self) -> str | None:
        return self.source.source_updated_at if self.source else None

    # Provisional-quality points that should not drive the trend / status verdict.
    _SOFT_REVISIONS = frozenset({"Estimated", "BudgetEstimate", "", None})

    @property
    def trend(self) -> str:
        """'up' | 'down' | 'flat', direction-aware (accounts for higher_is_better).

        Computed from the last two *firm* points (revision Actual / Provisional /
        Revised) so that estimated future-year figures don't fabricate a verdict.
        Falls back to any two points only if fewer than two firm points exist."""
        ordered = [p for p in sorted(self.series, key=lambda p: p.year) if p.value is not None]
        firm = [p for p in ordered if p.revision not in self._SOFT_REVISIONS]
        pts = firm if len(firm) >= 2 else ordered
        if len(pts) < 2:
            return "flat"
        delta = pts[-1].value - pts[-2].value
        if abs(delta) < 1e-9:
            return "flat"
        improving = delta > 0 if self.higher_is_better else delta < 0
        return "up" if improving else "down"


class KPISeriesPoint(Base):
    """One point of a curated multi-year analytics series for a KPI, used to
    render the ministry-detail charts. Distinct from KPIHistory (the live
    connector change-log): this is hand/seed-curated historical context
    (e.g. FY2014-15 through the latest FY) so trend, dual-axis and
    category-comparison charts have something to draw."""

    __tablename__ = "kpi_series_points"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kpi_id: Mapped[int] = mapped_column(ForeignKey("kpis.id"), nullable=False)

    year: Mapped[int] = mapped_column(Integer, nullable=False)
    period_label: Mapped[str] = mapped_column(String(20), nullable=False)

    value: Mapped[float | None] = mapped_column(Float, nullable=True)
    secondary_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    target_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    breakdown: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # Provenance of this point: Actual | Provisional | Revised | BudgetEstimate | Estimated
    revision: Mapped[str | None] = mapped_column(String(20), nullable=True)

    kpi: Mapped["KPI"] = relationship(back_populates="series")


class Event(Base):
    """Chart annotation: a marker for a notable year (COVID, a policy launch,
    etc). ministry_codes empty/null means it applies to every ministry."""

    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    category: Mapped[str] = mapped_column(String(30), default="policy")  # covid | policy | global
    ministry_codes: Mapped[list | None] = mapped_column(JSON, nullable=True)


class KPISource(Base):
    """Describes where a KPI's value comes from and how to extract it."""

    __tablename__ = "kpi_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kpi_id: Mapped[int] = mapped_column(ForeignKey("kpis.id"), unique=True, nullable=False)

    source_type: Mapped[str] = mapped_column(String(20), nullable=False)  # csv | excel | pdf | web
    location: Mapped[str] = mapped_column(String(1000), nullable=False)  # file path or URL
    parse_config: Mapped[dict] = mapped_column(JSON, default=dict)

    last_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_changed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # --- Phase 2 safeguards: mirrors app.kpi_specifications.KPISpec so the
    # data-quality/proxy status travels with the source row itself. ---------
    data_quality: Mapped[str | None] = mapped_column(String(10), nullable=True)  # HIGH | MEDIUM | LOW
    is_proxy: Mapped[bool] = mapped_column(Boolean, default=False)
    data_version: Mapped[str] = mapped_column(String(20), default="Final")  # Provisional | Revised | Final

    # --- Tier-A provenance surfaced to the dashboard ---------------------
    source_name: Mapped[str | None] = mapped_column(String(400), nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(600), nullable=True)
    source_cadence: Mapped[str | None] = mapped_column(String(120), nullable=True)
    source_updated_at: Mapped[str | None] = mapped_column(String(20), nullable=True)  # YYYY-MM of the figure behind current_value
    is_live: Mapped[bool] = mapped_column(Boolean, default=False)  # True = computed from a real curated data source

    kpi: Mapped["KPI"] = relationship(back_populates="source")


class MinistryInsight(Base):
    """Cached Claude-generated briefing for a ministry: 3 bullet points plus
    an inference paragraph. Regenerated only when the underlying KPI values
    change (tracked via kpi_snapshot_hash)."""

    __tablename__ = "ministry_insights"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ministry_id: Mapped[int] = mapped_column(ForeignKey("ministries.id"), unique=True, nullable=False)

    bullets: Mapped[list] = mapped_column(JSON, default=list)
    inference: Mapped[str] = mapped_column(Text, default="")
    kpi_snapshot_hash: Mapped[str] = mapped_column(String(64), default="")
    generated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )

    # --- Phase 2 safeguards: structured framework-driven verdict fields.
    # bullets/inference above are kept for backward compatibility with the
    # existing frontend (bullets == evidence, inference folds in headline +
    # forward_implications); the fields below carry the full structure. -----
    headline: Mapped[str] = mapped_column(String(20), default="")  # Good | Mediocre | Poor | Mixed
    time_period_judged: Mapped[str] = mapped_column(String(100), default="")
    caveats: Mapped[list] = mapped_column(JSON, default=list)
    proxy_disclosure: Mapped[str | None] = mapped_column(Text, nullable=True)
    data_quality_flag: Mapped[str] = mapped_column(String(10), default="MEDIUM")  # HIGH | MEDIUM | LOW
    comparative_context: Mapped[str] = mapped_column(Text, default="")
    forward_implications: Mapped[str] = mapped_column(Text, default="")
    framework_version: Mapped[str] = mapped_column(String(20), default="1.0")

    ministry: Mapped["Ministry"] = relationship(back_populates="insight")


class KPIHistory(Base):
    """Time series of KPI values, one row per detected value change (live
    connector change-log — see KPISeriesPoint for the curated analytics
    series used by charts)."""

    __tablename__ = "kpi_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kpi_id: Mapped[int] = mapped_column(ForeignKey("kpis.id"), nullable=False)

    value: Mapped[float] = mapped_column(Float, nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    source_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # --- Phase 2 audit trail: who/what produced this value point ------------
    source_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    data_version: Mapped[str | None] = mapped_column(String(20), nullable=True)
    extraction_confidence: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 0-100
    calculation_formula: Mapped[str | None] = mapped_column(String(500), nullable=True)
    audit_log: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON-encoded calc steps

    kpi: Mapped["KPI"] = relationship(back_populates="history")
