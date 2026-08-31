"""Ministry Performance Scoring System (0-100).

A transparent, economics-aware, fully-auditable scoring framework: each
ministry's composite score is a weighted average of 2-3 KPI sub-scores,
where the weights reflect relative economic importance (never equal by
default), sub-scores are direction-aware normalizations against an
aspirational/structural target, a modest trend adjustment rewards or
penalizes a clear multi-year direction, and a data-confidence multiplier
down-weights proxy or low-quality KPIs rather than letting them drive the
verdict.

This module intentionally does not import app.models (avoids a circular
import with Ministry.score) - it operates on duck-typed KPI/Ministry
objects exposing the same attributes as app.models.KPI / app.models.Ministry.

--- Normalization -----------------------------------------------------------

Higher-is-better:
    Score = clamp(100 * (Actual - Floor) / (Target - Floor), 0, 100)

Lower-is-better:
    Score = clamp(100 * (Ceiling - Actual) / (Ceiling - Target), 0, 100)

Target = the KPI's aspirational/structural target where one is on file,
falling back to the official target. Floor/Ceiling are reasonable
worst-case bounds chosen to keep outliers from producing extreme scores;
see MINISTRY_SCORING below for the specific bound and its rationale.

--- Trend adjustment ---------------------------------------------------------

Up to +/-8 points, added to a KPI's normalized score before weighting, based
on how consistently its last up to 5 curated series points moved in the
"improving" direction (respecting higher_is_better). This is intentionally
modest - it nudges the score toward multi-year direction without letting a
single recent uptick/downtick swamp the level-based read.

--- Data confidence multiplier -----------------------------------------------

Each KPI's configured weight is scaled by a confidence multiplier before the
weighted average is taken (HIGH=1.0, MEDIUM=0.85, LOW=0.6; proxy metrics
carry an additional x0.85). Down-weighted contributions are then
renormalized against the total effective weight actually available, so a
ministry missing/short on data is still scored out of 100, not silently
diluted by missing weight.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

DATA_CONFIDENCE = {"HIGH": 1.0, "MEDIUM": 0.85, "LOW": 0.6}
DEFAULT_CONFIDENCE = 0.75  # unknown/missing data_quality
PROXY_PENALTY = 0.85

# (min_inclusive, max_exclusive, label) - max_exclusive=101 so 100 itself lands in Strong.
SCORE_BANDS: tuple[tuple[float, float, str], ...] = (
    (80, 101, "Strong"),
    (65, 80, "Satisfactory"),
    (50, 65, "Mediocre"),
    (35, 50, "Weak"),
    (0, 35, "Poor"),
)


def score_label(score: float | None) -> str | None:
    if score is None:
        return None
    for lo, hi, label in SCORE_BANDS:
        if lo <= score < hi:
            return label
    return "Poor" if score < 0 else "Strong"


@dataclass(frozen=True)
class KPIWeight:
    """One KPI's role in its ministry's composite score."""

    kpi_name: str  # must match KPI.name exactly (see app/seed_dashboard.py)
    weight: float  # fraction of 1.0; weights for a ministry should sum to 1.0
    label: str  # the economic concept this KPI stands in for (for display/prompts)
    floor: float | None = None  # used when the KPI is higher-is-better
    ceiling: float | None = None  # used when the KPI is lower-is-better
    rationale: str = ""  # why this floor/ceiling/weight, for auditability


# ---------------------------------------------------------------------------
# Per-ministry weights. Every KPI referenced here must exist (by exact name)
# in app.seed_dashboard's seeded data. Floor/Ceiling bounds are deliberately
# conservative estimates of a genuine worst case (documented per KPI) rather
# than the observed min/max, so a single bad data point can't blow out the
# scale in either direction.
# ---------------------------------------------------------------------------

MINISTRY_SCORING: dict[str, list[KPIWeight]] = {
    "FIN": [
        KPIWeight(
            "Fiscal Deficit", 0.45, "Fiscal discipline",
            ceiling=9.5,
            rationale="COVID-year (FY2020-21) deficit peaked near 9.2% of GDP; 9.5 is a genuine crisis ceiling.",
        ),
        KPIWeight(
            "Tax Collection Growth", 0.35, "Structural tax buoyancy",
            floor=-5.0,
            rationale="A real YoY contraction in collections is a plausible worst case; 0% growth alone shouldn't zero the score.",
        ),
        KPIWeight(
            "Tax Harassment Cases", 0.20, "Tax administration quality (proxy)",
            ceiling=900.0,
            rationale="Proxy, LOW confidence by design - down-weighted via the confidence multiplier, not just the base weight.",
        ),
    ],
    "COMM": [
        KPIWeight(
            "Industrial Imports %", 0.45, "Net industrial import dependence",
            ceiling=40.0,
            rationale="40% would mark severe, structurally uncompetitive import reliance on non-oil/gold industrial goods.",
        ),
        KPIWeight(
            "Manufacturing Growth", 0.35, "Manufacturing GVA share/growth",
            floor=10.0,
            rationale="Manufacturing GVA share has not fallen below ~13-14% of GVA in the modern data; 10 is a safety floor.",
        ),
        KPIWeight(
            "PLI Effectiveness", 0.20, "PLI real value addition (proxy)",
            floor=0.0,
            rationale="Self-reported investment-realisation proxy; capped weight and floor at zero committed investment realised.",
        ),
    ],
    "RAIL": [
        KPIWeight(
            "Freight Volume Growth", 0.40, "Freight volume growth",
            floor=-5.0,
            rationale="FY2020-21 freight growth went negative; -5% YoY is a realistic contraction floor.",
        ),
        KPIWeight(
            "Rail Market Share", 0.35, "Rail modal share",
            floor=20.0,
            rationale="Rail's freight modal share has structurally declined toward the high-20s; 20 is a plausible structural floor.",
        ),
        KPIWeight(
            "Train Speeds & Capacity", 0.25, "Speed / capacity utilisation",
            floor=20.0,
            rationale="Composite speed/capacity index; 20 reflects a badly congested, low-speed network.",
        ),
    ],
    "POW": [
        KPIWeight(
            "Discom Financial Health", 0.45, "AT&C losses + ACS-ARR gap",
            ceiling=30.0,
            rationale="Pre-UDAY AT&C losses commonly ran 20-27%; 30 is a genuine distribution-utility distress ceiling.",
        ),
        KPIWeight(
            "Industrial Tariffs", 0.30, "Industrial tariff competitiveness",
            ceiling=10.0,
            rationale="High-tariff states have touched Rs9-10/kWh for industrial consumers; 10 marks uncompetitive pricing.",
        ),
        KPIWeight(
            "Power Availability", 0.25, "Reliability / availability",
            floor=85.0,
            rationale="Sustained sub-85% availability would indicate serious, chronic supply shortfalls.",
        ),
    ],
    "DEF": [
        KPIWeight(
            "Defence CapEx", 0.50, "Capital spend as % of GDP",
            floor=0.3,
            rationale="Capital outlay has not fallen below roughly 0.3% of GDP in the modern budget era.",
        ),
        KPIWeight(
            "Domestic MIC Development", 0.30, "True indigenisation / domestic content",
            floor=30.0,
            rationale="Officially-reported indigenisation is a claim, not an audited figure - floor reflects a low-indigenisation baseline.",
        ),
        KPIWeight(
            "Force Modernisation", 0.20, "Modernisation progress (proxy)",
            floor=30.0,
            rationale="Self-reported vintage/current/state-of-the-art split; LOW confidence, floor reflects a heavily-vintage fleet.",
        ),
    ],
    "EDU": [
        KPIWeight(
            "Learning Outcomes", 0.55, "Foundational learning outcomes",
            floor=15.0,
            rationale="ASER Std-3 reading levels have not fallen below the mid-teens even in COVID-disrupted rounds.",
        ),
        KPIWeight(
            "Enrollment Quality", 0.25, "Enrollment & transition quality",
            floor=30.0,
            rationale="Senior-secondary GER has structural drop-out well above a 30% floor even in weak states.",
        ),
        KPIWeight(
            "Exam Integrity", 0.20, "Exam system integrity (proxy)",
            ceiling=15.0,
            rationale="Compiled incident count, not an official register; 15 major incidents/year is a severe-integrity-crisis ceiling.",
        ),
    ],
    "SKILL": [
        KPIWeight(
            "Youth NEET Rate", 0.50, "Youth NEET rate",
            ceiling=40.0,
            rationale="A 40% youth NEET rate would mark a severe, economy-wide youth engagement crisis.",
        ),
        KPIWeight(
            "Job Creation", 0.30, "Formal job creation (youth proxy)",
            floor=0.0,
            rationale="EPFO net-addition proxy for formal job creation; floor at zero net formalisation.",
        ),
        KPIWeight(
            "Apprenticeship Utilisation", 0.20, "Apprenticeship / skilling effectiveness",
            floor=20.0,
            rationale="Apprenticeship budgets have chronically under-spent; 20% utilisation is a realistic weak-year floor.",
        ),
    ],
    "AGRI": [
        KPIWeight(
            "Real Farmer Income", 0.45, "Real farmer income / productivity",
            floor=100.0,
            rationale="Index base year 2014=100 - the floor is simply no real growth since the base year.",
        ),
        KPIWeight(
            "Food Inflation", 0.30, "Food inflation stability",
            ceiling=12.0,
            rationale="Food CPI has spiked into the low-to-mid teens in bad years; 12 marks a genuinely destabilising spell.",
        ),
        KPIWeight(
            "Ethanol Programme", 0.25, "Ethanol programme net benefit",
            floor=0.0,
            rationale="Blended-litres volume; floor at a pre-programme-acceleration zero baseline.",
        ),
    ],
    "PETRO": [
        KPIWeight(
            "Oil Import Dependence", 0.50, "Oil import dependence",
            ceiling=95.0,
            rationale="Dependence has hovered 85-88%; 95 marks near-total import reliance as the crisis ceiling.",
        ),
        KPIWeight(
            "Ethanol Blending %", 0.30, "Ethanol blending effectiveness",
            floor=0.0,
            rationale="Pre-programme blending was effectively 0%; a clean floor for the E20 push.",
        ),
        KPIWeight(
            "Refining Efficiency", 0.20, "Downstream efficiency",
            floor=70.0,
            rationale="Capacity utilisation sustained below 70% would indicate serious downstream underperformance.",
        ),
    ],
    "ROAD": [
        KPIWeight(
            "Logistics Cost %", 0.45, "Logistics cost as % of GDP",
            ceiling=16.0,
            rationale="India's logistics cost is widely cited in the 13-14% of GDP range; 16 is a conservative crisis ceiling.",
        ),
        KPIWeight(
            "Modal Share", 0.30, "Modal share improvement (rail/water vs road)",
            ceiling=75.0,
            rationale="Tracks road's own freight share (lower is better, i.e. rail/water gaining); 75 marks near-total road dominance.",
        ),
        KPIWeight(
            "Highway Construction", 0.25, "Highway construction quality & pace",
            floor=10.0,
            rationale="Sustained sub-10 km/day would mark a serious construction-pace collapse versus the historical 20-40 km/day range.",
        ),
    ],
}


@dataclass
class KPIContribution:
    kpi_name: str
    label: str
    normalized_score: float
    trend_adjustment: float
    adjusted_score: float
    base_weight: float
    confidence_multiplier: float
    effective_weight: float
    data_quality: str | None
    is_proxy: bool
    target_used: float | None
    target_is_aspirational: bool


@dataclass
class MinistryScoreResult:
    ministry_code: str
    composite_score: float | None
    label: str | None
    contributions: list[KPIContribution] = field(default_factory=list)


def _target_for(kpi: Any) -> tuple[float | None, bool]:
    """(target, is_aspirational) - prefer the aspirational/structural target."""
    aspirational = getattr(kpi, "aspirational_target", None)
    if aspirational is not None:
        return aspirational, True
    return getattr(kpi, "target_value", None), False


def _normalized_score(kpi: Any, cfg: KPIWeight, target: float) -> float | None:
    actual = getattr(kpi, "current_value", None)
    if actual is None:
        return None
    higher_is_better = getattr(kpi, "higher_is_better", True)
    if higher_is_better:
        floor = cfg.floor if cfg.floor is not None else 0.0
        if target == floor:
            return 100.0
        raw = 100.0 * (actual - floor) / (target - floor)
    else:
        ceiling = cfg.ceiling if cfg.ceiling is not None else target * 2
        if ceiling == target:
            return 100.0
        raw = 100.0 * (ceiling - actual) / (ceiling - target)
    return max(0.0, min(100.0, raw))


def _trend_adjustment(kpi: Any) -> float:
    """+/-8 (or +/-6 on thinner data) if the last up to 5 curated series
    points move consistently in the improving direction; 0 otherwise."""
    series = list(getattr(kpi, "series", []) or [])
    points = sorted((p for p in series if getattr(p, "value", None) is not None), key=lambda p: p.year)
    points = points[-5:]
    if len(points) < 3:
        return 0.0

    higher_is_better = getattr(kpi, "higher_is_better", True)
    moves = []
    for a, b in zip(points, points[1:]):
        delta = b.value - a.value
        if abs(delta) < 1e-9:
            continue
        moves.append((delta > 0) if higher_is_better else (delta < 0))
    if not moves:
        return 0.0

    improving_frac = sum(moves) / len(moves)
    strong = len(moves) >= 4
    if improving_frac >= 0.75:
        return 8.0 if strong else 6.0
    if improving_frac <= 0.25:
        return -8.0 if strong else -6.0
    return 0.0


def _confidence_multiplier(kpi: Any) -> float:
    quality = getattr(kpi, "data_quality", None)
    mult = DATA_CONFIDENCE.get(quality, DEFAULT_CONFIDENCE)
    if getattr(kpi, "is_proxy", False):
        mult *= PROXY_PENALTY
    return mult


def compute_ministry_score(ministry: Any) -> MinistryScoreResult:
    """Compute the weighted, confidence-adjusted, trend-adjusted composite
    score (0-100) for a ministry, per MINISTRY_SCORING. Returns
    composite_score=None (and no label) if the ministry has no scoring
    config on file or none of its configured KPIs have data."""
    cfgs = MINISTRY_SCORING.get(getattr(ministry, "code", None))
    if not cfgs:
        return MinistryScoreResult(getattr(ministry, "code", ""), None, None, [])

    by_name = {k.name: k for k in getattr(ministry, "kpis", [])}
    contributions: list[KPIContribution] = []

    for cfg in cfgs:
        kpi = by_name.get(cfg.kpi_name)
        if kpi is None:
            continue
        target, is_aspirational = _target_for(kpi)
        if target is None:
            continue
        normalized = _normalized_score(kpi, cfg, target)
        if normalized is None:
            continue
        trend_adj = _trend_adjustment(kpi)
        adjusted = max(0.0, min(100.0, normalized + trend_adj))
        confidence = _confidence_multiplier(kpi)
        effective_weight = cfg.weight * confidence

        contributions.append(
            KPIContribution(
                kpi_name=cfg.kpi_name,
                label=cfg.label,
                normalized_score=round(normalized, 1),
                trend_adjustment=trend_adj,
                adjusted_score=round(adjusted, 1),
                base_weight=cfg.weight,
                confidence_multiplier=round(confidence, 2),
                effective_weight=round(effective_weight, 4),
                data_quality=getattr(kpi, "data_quality", None),
                is_proxy=bool(getattr(kpi, "is_proxy", False)),
                target_used=target,
                target_is_aspirational=is_aspirational,
            )
        )

    total_effective_weight = sum(c.effective_weight for c in contributions)
    if not total_effective_weight:
        return MinistryScoreResult(ministry.code, None, None, contributions)

    composite = sum(c.adjusted_score * c.effective_weight for c in contributions) / total_effective_weight
    composite = round(max(0.0, min(100.0, composite)), 1)
    return MinistryScoreResult(ministry.code, composite, score_label(composite), contributions)
