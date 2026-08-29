from datetime import datetime

from pydantic import BaseModel, ConfigDict


class KPIOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    category: str
    unit: str
    current_value: float
    target_value: float
    period: str
    updated_at: datetime

    chart_type: str
    data_shape: str
    hero: bool
    higher_is_better: bool
    secondary_label: str | None = None
    secondary_unit: str | None = None
    benchmark_label: str | None = None
    breakdown_label: str | None = None

    display_title: str | None = None
    plain_note: str | None = None
    aspirational_target: float | None = None
    aspirational_label: str | None = None

    progress_pct: float | None = None
    trend: str

    # provenance (populated for Tier-A KPIs; null otherwise)
    is_live: bool = False
    data_quality: str | None = None
    is_proxy: bool = False
    data_version: str | None = None
    source_name: str | None = None
    source_url: str | None = None
    source_cadence: str | None = None
    source_updated_at: str | None = None


class MinistryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    code: str
    description: str
    score: float | None = None
    score_label: str | None = None
    status: str


class MinistryDetailOut(MinistryOut):
    kpis: list[KPIOut] = []


class KPIScoreContributionOut(BaseModel):
    kpi_name: str
    label: str
    normalized_score: float
    trend_adjustment: float
    adjusted_score: float
    base_weight: float
    confidence_multiplier: float
    effective_weight: float
    data_quality: str | None = None
    is_proxy: bool = False
    target_used: float | None = None
    target_is_aspirational: bool = False


class MinistryScoreBreakdownOut(BaseModel):
    ministry: str
    ministry_code: str
    composite_score: float | None = None
    label: str | None = None
    contributions: list[KPIScoreContributionOut] = []


class InsightsResponse(BaseModel):
    ministry: str
    bullets: list[str]
    inference: str
    generated_at: datetime
    cached: bool

    # Phase 2 safeguard fields (see app/analysis_frameworks.py, app/kpi_specifications.py)
    headline: str = ""
    time_period_judged: str = ""
    caveats: list[str] = []
    proxy_disclosure: str | None = None
    data_quality_flag: str = "MEDIUM"
    comparative_context: str = ""
    forward_implications: str = ""


class KPIHistoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    value: float
    recorded_at: datetime


class KPISeriesPointOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    year: int
    period_label: str
    value: float | None = None
    secondary_value: float | None = None
    target_value: float | None = None
    breakdown: dict | None = None
    revision: str | None = None


class KpiProvenanceOut(BaseModel):
    kpi_id: int
    kpi_name: str
    display_title: str | None = None
    plain_note: str | None = None
    ministry_code: str
    is_live: bool
    data_quality: str | None = None
    is_proxy: bool = False
    source_name: str | None = None
    source_url: str | None = None
    source_cadence: str | None = None
    data_version: str | None = None
    source_updated_at: str | None = None
    official_target: float | None = None
    official_target_label: str | None = None
    aspirational_target: float | None = None
    aspirational_label: str | None = None
    definition: str | None = None
    formula: str | None = None
    caveats: list[str] = []
    audit: list[dict] = []
    unresolved: list[dict] = []
    datasets: list[str] = []


class EventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    label: str
    year: int
    category: str


class SummaryMinistryOut(BaseModel):
    id: int
    code: str
    name: str
    score: float | None = None
    score_label: str | None = None
    status: str


class SummaryOut(BaseModel):
    overall_score: float | None = None
    overall_label: str | None = None
    total_ministries: int
    improving_count: int
    declining_count: int
    steady_count: int
    top_ministries: list[SummaryMinistryOut]
    bottom_ministries: list[SummaryMinistryOut]


class SyncResultOut(BaseModel):
    kpi_name: str
    ministry_code: str = ""
    status: str
    old_value: float | None = None
    new_value: float | None = None
    message: str = ""


class ChatMessageIn(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str
    ministry_id: int | None = None
    history: list[ChatMessageIn] = []


class ChatResponse(BaseModel):
    reply: str


# --- Tarka chatbot -----------------------------------------------------------


class TarkaAnswerOut(BaseModel):
    """Structured Headline | Evidence | Caveats | Context | Implications answer."""

    headline: str
    evidence: list[str] = []
    caveats: list[str] = []
    comparative_context: str = ""
    forward_implications: str = ""
    time_period_judged: str = ""
    data_quality_flag: str = "MEDIUM"
    proxy_disclosure: str | None = None


class TarkaQuestionRequest(BaseModel):
    ministry_id: int
    question: str


class TarkaCompareRequest(BaseModel):
    ministry_id_1: int
    ministry_id_2: int
    aspect: str = ""


class TarkaExplainRequest(BaseModel):
    ministry_id: int
    kpi_name: str


class TarkaTrendRequest(BaseModel):
    ministry_id: int
    time_period: str = ""


class TarkaFocusOut(BaseModel):
    ministry: str
    focus_areas: list[str] = []
    rationale: str = ""
