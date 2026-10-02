import logging

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session, selectinload

from app.claude_service import chat_reply, get_or_generate_insights
from app.config import settings
from app.database import Base, SessionLocal, engine, get_db, scrub_stored_em_dashes, sync_schema
from app.models import KPI, Event, KPISeriesPoint, Ministry
from app.pipeline.sync_service import sync_all, sync_ministry
from app.schemas import (
    ChatRequest,
    ChatResponse,
    EventOut,
    InsightsResponse,
    KpiProvenanceOut,
    KPIScoreContributionOut,
    KPISeriesPointOut,
    MinistryDetailOut,
    MinistryOut,
    MinistryScoreBreakdownOut,
    SummaryMinistryOut,
    SummaryOut,
    SyncResultOut,
    TarkaAnswerOut,
    TarkaCompareRequest,
    TarkaExplainRequest,
    TarkaFocusOut,
    TarkaQuestionRequest,
    TarkaTrendRequest,
)
from app.scoring import score_label
from app.tarka_chatbot import (
    answer_performance_question,
    compare_ministries,
    explain_kpi,
    generate_trend_analysis,
    suggest_focus_areas,
)

logger = logging.getLogger("vik_isit.boot")

# These three only ever ALTER/scrub what's already there - never required for the
# ASGI app itself to exist. If the database is unreachable (expired free instance,
# host down, credentials rotated) none of them must be allowed to block app
# creation: a bare `create_engine()` doesn't connect, but the first real query
# inside create_all() does, and on a dead host that can hang far longer than any
# platform health-check timeout. Previously that meant the whole process never
# finished importing, so uvicorn never bound the port and *every* route - not
# just DB-backed ones - was unreachable from the outside, which is what a
# platform reports as "server failure" rather than a clear error. Catching here
# means the app always starts, /health always answers fast, and DB-dependent
# routes fail individually with a real error instead of the whole service
# vanishing. See /health/db below for an explicit, on-demand DB check.
try:
    Base.metadata.create_all(bind=engine)
    sync_schema()
    scrub_stored_em_dashes()
except Exception:  # noqa: BLE001 - must never prevent the app from starting
    logger.exception(
        "Startup DB initialization failed - the API will still start, but routes that "
        "touch the database will fail until this is fixed. Check DATABASE_URL and that "
        "the database itself is reachable (a free-tier Postgres instance that expired "
        "or was deleted is the most common cause)."
    )

app = FastAPI(
    title="vik-isit API",
    description="Backend for the vik-isit ministry performance analysis platform: KPI tracking and AI-driven insights.",
    version="0.3.0",
)

app.add_middleware(
    CORSMiddleware,
    # Local-dev origins are always allowed; add your deployed frontend's URL
    # (e.g. https://your-app.vercel.app) via the CORS_ORIGINS env var on the
    # backend host - comma-separated if you have more than one (prod + preview).
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", *settings.cors_origin_list],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

RANGE_YEARS = {"5y": 5, "10y": 10, "full": None}

# GET responses this app serves change at most daily (data syncs are manual /
# weekly). A short reuse window plus a brief serve-stale-while-revalidating grace
# keeps the UI snappy without letting a stale copy linger. The real cold-start
# defense is the frontend's localStorage cache (queryPersist.js). Not applied to
# /health (used by the keep-alive ping).
_CACHEABLE_MISS = ("/health", "/docs", "/openapi.json", "/redoc")


@app.middleware("http")
async def cache_headers(request, call_next):
    response = await call_next(request)
    if (
        request.method == "GET"
        and response.status_code == 200
        and not request.url.path.startswith(_CACHEABLE_MISS)
        and "cache-control" not in response.headers
    ):
        response.headers["Cache-Control"] = "public, max-age=60, stale-while-revalidate=120"
    return response


@app.get("/health")
def health_check():
    # Deliberately DB-free: this is what the keep-alive ping and the platform's
    # own health check hit, and it must answer fast even while the database is
    # down - see /health/db for the version that actually checks the database.
    return {"status": "ok"}


@app.get("/health/db")
def health_check_db():
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
        return {"status": "ok", "database": "reachable"}
    except Exception as exc:  # noqa: BLE001 - this route's entire job is to report the failure
        raise HTTPException(status_code=503, detail=f"database unreachable: {exc}") from exc


# Ministry.score / .status / .trend all walk every KPI and its series, so any
# endpoint that touches them for a whole list would otherwise fire dozens of
# lazy-load queries (N+1). Pull the graph in one shot instead.
def _ministry_graph(db: Session):
    return db.query(Ministry).options(
        selectinload(Ministry.kpis).selectinload(KPI.series),
        selectinload(Ministry.kpis).selectinload(KPI.source),
    )


@app.get("/ministries", response_model=list[MinistryOut])
def list_ministries(db: Session = Depends(get_db)):
    return _ministry_graph(db).order_by(Ministry.name).all()


@app.get("/ministries/{ministry_id}", response_model=MinistryDetailOut)
def get_ministry(ministry_id: int, db: Session = Depends(get_db)):
    ministry = _ministry_graph(db).filter(Ministry.id == ministry_id).first()
    if not ministry:
        raise HTTPException(status_code=404, detail="Ministry not found.")
    return ministry


@app.get("/summary", response_model=SummaryOut)
def get_summary(db: Session = Depends(get_db)):
    ministries = _ministry_graph(db).all()
    scored = [m for m in ministries if m.score is not None]
    overall = round(sum(m.score for m in scored) / len(scored), 1) if scored else None

    improving = sum(1 for m in ministries if m.status == "improving")
    declining = sum(1 for m in ministries if m.status == "declining")
    steady = len(ministries) - improving - declining

    ranked = sorted(scored, key=lambda m: m.score, reverse=True)
    to_summary = lambda m: SummaryMinistryOut(
        id=m.id, code=m.code, name=m.name, score=m.score, score_label=m.score_label, status=m.status
    )

    return SummaryOut(
        overall_score=overall,
        overall_label=score_label(overall),
        total_ministries=len(ministries),
        improving_count=improving,
        declining_count=declining,
        steady_count=steady,
        top_ministries=[to_summary(m) for m in ranked[:3]],
        bottom_ministries=[to_summary(m) for m in ranked[-3:][::-1]] if len(ranked) > 3 else [],
    )


@app.get("/events", response_model=list[EventOut])
def list_events(ministry_code: str | None = None, db: Session = Depends(get_db)):
    events = db.query(Event).order_by(Event.year).all()
    if ministry_code:
        events = [e for e in events if not e.ministry_codes or ministry_code in e.ministry_codes]
    return events


@app.post("/ministries/{ministry_id}/insights", response_model=InsightsResponse)
def get_ministry_insights(ministry_id: int, force: bool = False, db: Session = Depends(get_db)):
    ministry = db.query(Ministry).filter(Ministry.id == ministry_id).first()
    if not ministry:
        raise HTTPException(status_code=404, detail="Ministry not found.")

    insight, cached = get_or_generate_insights(db, ministry, force=force)

    return InsightsResponse(
        ministry=ministry.name,
        bullets=insight.bullets,
        inference=insight.inference,
        generated_at=insight.generated_at,
        cached=cached,
        headline=insight.headline,
        time_period_judged=insight.time_period_judged,
        caveats=insight.caveats,
        proxy_disclosure=insight.proxy_disclosure,
        data_quality_flag=insight.data_quality_flag,
        comparative_context=insight.comparative_context,
        forward_implications=insight.forward_implications,
    )


@app.get("/ministries/{ministry_id}/score-breakdown", response_model=MinistryScoreBreakdownOut)
def get_ministry_score_breakdown(ministry_id: int, db: Session = Depends(get_db)):
    """The exact formula and assumptions behind a ministry's composite score:
    per-KPI weight, normalization, trend adjustment, and confidence
    multiplier - see app.scoring for the full methodology."""
    ministry = db.query(Ministry).filter(Ministry.id == ministry_id).first()
    if not ministry:
        raise HTTPException(status_code=404, detail="Ministry not found.")

    result = ministry._score_result
    return MinistryScoreBreakdownOut(
        ministry=ministry.name,
        ministry_code=ministry.code,
        composite_score=result.composite_score,
        label=result.label,
        contributions=[KPIScoreContributionOut(**vars(c)) for c in result.contributions],
    )


@app.post("/chat", response_model=ChatResponse)
def chat_endpoint(payload: ChatRequest, db: Session = Depends(get_db)):
    ministry = None
    if payload.ministry_id is not None:
        ministry = db.query(Ministry).filter(Ministry.id == payload.ministry_id).first()
        if not ministry:
            raise HTTPException(status_code=404, detail="Ministry not found.")

    all_ministries = db.query(Ministry).order_by(Ministry.name).all()
    reply = chat_reply(payload.message, payload.history, ministry, all_ministries)
    return ChatResponse(reply=reply)


def _get_ministry_or_404(db: Session, ministry_id: int) -> Ministry:
    ministry = db.query(Ministry).filter(Ministry.id == ministry_id).first()
    if not ministry:
        raise HTTPException(status_code=404, detail="Ministry not found.")
    return ministry


@app.post("/tarka/ask", response_model=TarkaAnswerOut)
def tarka_ask(payload: TarkaQuestionRequest, db: Session = Depends(get_db)):
    ministry = _get_ministry_or_404(db, payload.ministry_id)
    return TarkaAnswerOut(**answer_performance_question(ministry, payload.question))


@app.post("/tarka/compare", response_model=TarkaAnswerOut)
def tarka_compare(payload: TarkaCompareRequest, db: Session = Depends(get_db)):
    m1 = _get_ministry_or_404(db, payload.ministry_id_1)
    m2 = _get_ministry_or_404(db, payload.ministry_id_2)
    return TarkaAnswerOut(**compare_ministries(m1, m2, payload.aspect))


@app.post("/tarka/explain", response_model=TarkaAnswerOut)
def tarka_explain(payload: TarkaExplainRequest, db: Session = Depends(get_db)):
    ministry = _get_ministry_or_404(db, payload.ministry_id)
    return TarkaAnswerOut(**explain_kpi(payload.kpi_name, ministry))


@app.post("/tarka/trend", response_model=TarkaAnswerOut)
def tarka_trend(payload: TarkaTrendRequest, db: Session = Depends(get_db)):
    ministry = _get_ministry_or_404(db, payload.ministry_id)
    return TarkaAnswerOut(**generate_trend_analysis(ministry, payload.time_period))


@app.get("/tarka/focus/{ministry_id}", response_model=TarkaFocusOut)
def tarka_focus(ministry_id: int, db: Session = Depends(get_db)):
    ministry = _get_ministry_or_404(db, ministry_id)
    result = suggest_focus_areas(ministry)
    return TarkaFocusOut(
        ministry=ministry.name,
        focus_areas=result.get("summary") or result.get("evidence", []),
        rationale=result.get("forward_implications") or result.get("comparative_context", ""),
    )


def _refresh_insights_for_updated_ministries(db: Session, results: list) -> None:
    """Best-effort regeneration of cached briefings for ministries whose KPI
    values changed during a sync. Failures here (e.g. no API key configured)
    must not fail the sync request itself."""
    updated_codes = {r.ministry_code for r in results if r.status == "updated" and r.ministry_code}
    for code in updated_codes:
        ministry = db.query(Ministry).filter(Ministry.code == code).first()
        if not ministry:
            continue
        try:
            get_or_generate_insights(db, ministry)
        except HTTPException:
            pass


@app.get("/kpis/{kpi_id}/history", response_model=list[KPISeriesPointOut])
def get_kpi_history(kpi_id: int, range: str = Query("full", pattern="^(5y|10y|full)$"), db: Session = Depends(get_db)):
    kpi = db.query(KPI).filter(KPI.id == kpi_id).first()
    if not kpi:
        raise HTTPException(status_code=404, detail="KPI not found.")

    points = db.query(KPISeriesPoint).filter(KPISeriesPoint.kpi_id == kpi_id).order_by(KPISeriesPoint.year).all()

    n = RANGE_YEARS[range]
    if n is not None and len(points) > n:
        points = points[-n:]
    return points


@app.get("/kpis/{kpi_id}/provenance", response_model=KpiProvenanceOut)
def get_kpi_provenance(kpi_id: int, db: Session = Depends(get_db)):
    kpi = db.query(KPI).filter(KPI.id == kpi_id).first()
    if not kpi:
        raise HTTPException(status_code=404, detail="KPI not found.")

    from app.kpi_specifications import get_kpi_spec

    ministry_code = kpi.ministry.code
    doc_spec = get_kpi_spec(ministry_code, kpi.name)
    out = KpiProvenanceOut(
        kpi_id=kpi.id,
        kpi_name=kpi.name,
        display_title=kpi.display_title,
        plain_note=kpi.plain_note,
        ministry_code=ministry_code,
        is_live=kpi.is_live,
        data_quality=kpi.data_quality,
        is_proxy=kpi.is_proxy,
        source_name=kpi.source_name,
        source_url=kpi.source_url,
        source_cadence=kpi.source_cadence,
        data_version=kpi.data_version,
        source_updated_at=kpi.source_updated_at,
        official_target=kpi.target_value or None,
        official_target_label=kpi.benchmark_label,
        aspirational_target=kpi.aspirational_target,
        aspirational_label=kpi.aspirational_label,
        definition=doc_spec.definition if doc_spec else None,
        formula=doc_spec.formula if doc_spec else None,
        caveats=list(doc_spec.caveats) if doc_spec else [],
    )

    if kpi.is_live and kpi.source and kpi.source.source_type in ("tier_a", "tier_b"):
        try:
            if kpi.source.source_type == "tier_b":
                from app.connectors.tier_b import compute_kpi
                from app.connectors.tier_b.spec import TIER_B_BY_NAME as TIER_BY_NAME
            else:
                from app.connectors.tier_a import compute_kpi
                from app.connectors.tier_a.spec import TIER_A_BY_NAME as TIER_BY_NAME

            spec = TIER_BY_NAME.get((ministry_code, kpi.name))
            if spec is not None:
                series = compute_kpi(spec.key)
                out.datasets = series.dataset_paths
                out.unresolved = series.unresolved
                out.audit = [
                    {
                        "period": a.period,
                        "formula": a.formula,
                        "inputs": a.inputs,
                        "output": a.output,
                        "source_doc": a.source_doc,
                        "source_url": a.source_url,
                        "page_ref": a.page_ref,
                        "revision": a.revision,
                    }
                    for a in series.audit
                ]
                if series.audit:
                    out.formula = out.formula or series.audit[-1].formula
        except Exception:  # noqa: BLE001 - provenance view is best-effort
            pass

    return out


@app.post("/sync/{ministry_code}", response_model=list[SyncResultOut])
def sync_ministry_endpoint(ministry_code: str, db: Session = Depends(get_db)):
    try:
        results = sync_ministry(db, ministry_code)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    _refresh_insights_for_updated_ministries(db, results)

    return [
        SyncResultOut(
            kpi_name=r.kpi_name,
            ministry_code=r.ministry_code,
            status=r.status,
            old_value=r.old_value,
            new_value=r.new_value,
            message=r.message,
        )
        for r in results
    ]


@app.post("/sync", response_model=list[SyncResultOut])
def sync_all_endpoint(db: Session = Depends(get_db)):
    results = sync_all(db)

    _refresh_insights_for_updated_ministries(db, results)

    return [
        SyncResultOut(
            kpi_name=r.kpi_name,
            ministry_code=r.ministry_code,
            status=r.status,
            old_value=r.old_value,
            new_value=r.new_value,
            message=r.message,
        )
        for r in results
    ]
