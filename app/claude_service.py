import hashlib
import json
from datetime import datetime, timezone

import anthropic
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.analysis_frameworks import CORE_ANALYTICAL_PRINCIPLES, format_framework_for_prompt, get_framework
from app.config import settings
from app.kpi_specifications import get_kpi_spec
from app.models import KPI, Ministry, MinistryInsight

MODEL = "claude-opus-5"
CHAT_MODEL = "claude-sonnet-5"

DEMO_DATA_DISCLOSURE = (
    "Data provenance varies by KPI. Tier-A KPIs (Finance, Petroleum, Agriculture, Railways, "
    "Power) are computed from curated official sources (Economic Survey/Budget, PPAC, MoSPI, "
    "Indian Railways, PFC, CEA) and each figure carries a revision status "
    "(Actual/Provisional/Revised/BudgetEstimate/Estimated) — treat Estimated/BudgetEstimate "
    "figures as provisional and say so. KPIs for the other five ministries are still "
    "illustrative placeholder data; if the user leans on those, note that they are not yet "
    "wired to a live source."
)


def _core_principles_block() -> str:
    return "\n".join(f"{i}. {p}" for i, p in enumerate(CORE_ANALYTICAL_PRINCIPLES, 1))


def _format_kpi_block(kpis: list[KPI], ministry_code: str) -> str:
    lines = []
    for kpi in kpis:
        spec = get_kpi_spec(ministry_code, kpi.name)
        quality = kpi.data_quality or (spec.data_quality if spec else "UNKNOWN")
        proxy = " [PROXY METRIC]" if (kpi.is_proxy or (spec and spec.proxy_based)) else ""
        title = kpi.display_title or kpi.name
        tgt = f"official target {kpi.target_value}{kpi.unit}" if kpi.target_value else "no hard target"
        if kpi.aspirational_target is not None:
            tgt += f", aspirational {kpi.aspirational_target}{kpi.unit}"
        rev = f", data status={kpi.data_version}" if kpi.data_version else ""
        lines.append(
            f"- {title} ({kpi.name}; {kpi.category}): current={kpi.current_value}{kpi.unit} "
            f"[{kpi.period}], {tgt}, trend={kpi.trend}, data_quality={quality}{proxy}{rev}"
        )
    return "\n".join(lines)


def _kpi_caveats_block(kpis: list[KPI], ministry_code: str) -> str:
    lines = []
    for kpi in kpis:
        spec = get_kpi_spec(ministry_code, kpi.name)
        if spec and spec.caveats:
            lines.append(f"- {kpi.name}: " + " | ".join(spec.caveats))
    return "\n".join(lines) if lines else "(no KPI-specific caveats on file)"


def _score_block(ministry: Ministry) -> str:
    """Render the deterministic Ministry Performance Score (0-100) — composite
    value, label, and per-KPI weighted breakdown — for the prompt. This is
    computed by app.scoring, not by Claude; Claude's job is to explain and
    contextualize it, not to invent a competing verdict."""
    result = ministry._score_result
    if result.composite_score is None:
        return "No composite score is configured for this ministry yet."

    lines = [f"Composite score: {result.composite_score}/100 — {result.label}"]
    for c in result.contributions:
        target_kind = "aspirational" if c.target_is_aspirational else "official"
        proxy_note = ", PROXY" if c.is_proxy else ""
        lines.append(
            f"  - {c.kpi_name} ({c.label}): weight={c.base_weight:.0%} x confidence={c.confidence_multiplier:.2f}"
            f"{proxy_note} (data_quality={c.data_quality or 'UNKNOWN'}) -> effective weight={c.effective_weight:.1%}; "
            f"normalized={c.normalized_score:.1f}/100 vs {target_kind} target={c.target_used}, "
            f"trend_adjustment={c.trend_adjustment:+.0f}, adjusted={c.adjusted_score:.1f}/100"
        )
    return "\n".join(lines)


def _kpi_snapshot_hash(kpis: list[KPI]) -> str:
    """Fingerprint of the KPI values a briefing was generated from, so a
    cached insight can be reused until the underlying data actually moves."""
    snapshot = "|".join(f"{kpi.id}:{kpi.current_value}" for kpi in sorted(kpis, key=lambda k: k.id))
    return hashlib.sha256(snapshot.encode()).hexdigest()


INSIGHT_JSON_CONTRACT = (
    'Respond with ONLY a JSON object (no markdown code fences, no other text before or after) '
    "with exactly this shape:\n"
    "{\n"
    '  "headline": "Good" | "Mediocre" | "Poor" | "Mixed",\n'
    '  "time_period_judged": "...",\n'
    '  "key_evidence": ["...", "...", "..."],\n'
    '  "important_caveats": ["...", "..."],\n'
    '  "proxy_disclosure": "..." or null,\n'
    '  "comparative_context": "...",\n'
    '  "forward_implications": "...",\n'
    '  "data_quality_notes": "HIGH" | "MEDIUM" | "LOW"\n'
    "}\n\n"
    "Rules:\n"
    '- "headline" is informational only — the app computes the authoritative composite score and '
    "label itself (given to you below); pick whichever of the four values best matches that label "
    "(Strong/Satisfactory -> Good, Mediocre -> Mediocre, Weak/Poor -> Poor, or Mixed if the KPIs "
    "pull in sharply different directions).\n"
    '- "key_evidence" must contain EXACTLY 3 strings, each referencing an actual KPI name and '
    "figures (values, targets, progress %) from the data given. Do not invent data. The FIRST "
    "string MUST state the ministry's composite score and label (given below) and name the "
    "single largest weighted contributor to it, by name and effective weight.\n"
    '- "important_caveats" must contain AT LEAST 1 caveat, drawn from (or consistent with) the '
    "caveats listed below for this ministry's KPIs and framework. Prefer a caveat about a "
    "down-weighted proxy/LOW-quality KPI when one materially affects the score.\n"
    '- "time_period_judged" must be a concrete period (e.g. "FY2014-15 to FY2025-26"), never the '
    "word 'recent' or 'current' alone.\n"
    '- "proxy_disclosure" MUST be non-null and MUST explicitly say "best available proxy for X '
    'because Y" if ANY of the KPIs used is a proxy metric (marked [PROXY METRIC] below); '
    "otherwise it must be null.\n"
    '- "comparative_context" should compare the ministry against BOTH its official target and its '
    "aspirational/structural target (both given below), not just one.\n"
    '- "forward_implications" should distinguish which of the ministry\'s recent KPI movements are '
    "cyclical (commodity swings, base effects, one-off receipts) versus structural (genuine "
    "capacity/productivity/institutional change).\n"
    '- "data_quality_notes" must reflect the LOWEST data_quality among the KPIs actually cited '
    "in key_evidence (i.e. don't claim HIGH confidence off a LOW-quality proxy)."
)


def _call_claude(ministry: Ministry) -> dict:
    if not settings.anthropic_api_key:
        raise HTTPException(
            status_code=503,
            detail="ANTHROPIC_API_KEY is not configured on the server.",
        )

    if not ministry.kpis:
        raise HTTPException(
            status_code=400,
            detail=f"{ministry.name} has no KPIs to analyze.",
        )

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    framework = get_framework(ministry.code)
    framework_block = format_framework_for_prompt(framework) if framework else "(no framework on file for this ministry)"
    kpi_block = _format_kpi_block(ministry.kpis, ministry.code)
    caveats_block = _kpi_caveats_block(ministry.kpis, ministry.code)
    score_block = _score_block(ministry)

    user_prompt = (
        f"Ministry: {ministry.name} ({ministry.code})\n"
        f"Description: {ministry.description}\n\n"
        f"Ministry Performance Score (computed by the app, not by you):\n{score_block}\n\n"
        f"KPI data:\n{kpi_block}\n\n"
        f"Per-KPI caveats on file:\n{caveats_block}\n\n"
        "Analyze this ministry's performance data using the framework and principles in the "
        "system prompt, and return the required JSON."
    )

    system_prompt = (
        "You are a senior Indian macroeconomic analyst. You evaluate ministry performance using a "
        "transparent, weighted KPI scoring system (0-100) that prioritises structural outcomes over "
        "optics. The composite score and its KPI-by-KPI breakdown are computed deterministically by "
        "the app and given to you below — treat them as ground truth, do not recompute or contradict "
        "them; your job is to explain and contextualize them.\n\n"
        "When generating insights:\n"
        "- Always reference the ministry's composite score and label from the breakdown given below.\n"
        "- Break down the contribution of each KPI — name the largest weighted driver.\n"
        "- Explicitly state the most important caveats and data-quality limitations.\n"
        "- Distinguish cyclical noise from structural trends.\n"
        "- Compare against both the official target and the aspirational/structural target.\n"
        "- Never treat equal weights as default — respect the economic-importance weights given.\n"
        "- If a KPI is proxy-based or incomplete, its effective weight is already reduced below — "
        "say so explicitly rather than treating it as equally reliable.\n"
        "- Maintain analytical independence: judge the data and the framework, not any government.\n\n"
        f"Core analytical principles:\n{_core_principles_block()}\n\n"
        f"Analytical framework for {ministry.name}:\n{framework_block}\n\n"
        f"{DEMO_DATA_DISCLOSURE}\n\n"
        f"{INSIGHT_JSON_CONTRACT}"
    )

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=1536,
            output_config={"effort": "medium"},
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
    except anthropic.AuthenticationError:
        raise HTTPException(status_code=502, detail="Invalid Anthropic API key.")
    except anthropic.RateLimitError:
        raise HTTPException(status_code=429, detail="Claude API rate limit hit, try again shortly.")
    except anthropic.APIStatusError as e:
        raise HTTPException(status_code=502, detail=f"Claude API error: {e.message}")

    text = "".join(block.text for block in response.content if block.type == "text").strip()

    try:
        data = json.loads(text)
        headline = str(data["headline"])
        time_period_judged = str(data["time_period_judged"])
        evidence = [str(b) for b in data["key_evidence"]]
        caveats = [str(c) for c in data["important_caveats"]]
        proxy_disclosure = data.get("proxy_disclosure")
        proxy_disclosure = str(proxy_disclosure) if proxy_disclosure else None
        comparative_context = str(data.get("comparative_context", ""))
        forward_implications = str(data.get("forward_implications", ""))
        data_quality_notes = str(data.get("data_quality_notes", "MEDIUM"))
    except (json.JSONDecodeError, KeyError, TypeError):
        raise HTTPException(status_code=502, detail="Claude returned an unexpected response format.")

    if len(evidence) != 3:
        raise HTTPException(status_code=502, detail="Claude did not return exactly 3 evidence points.")
    if not caveats:
        raise HTTPException(status_code=502, detail="Claude did not return any caveats.")

    # The deterministic Ministry Performance Score label (app.scoring) is authoritative —
    # it always wins over whatever Claude picked for "headline", so the badge shown here
    # never disagrees with the score shown elsewhere in the dashboard.
    score_result = ministry._score_result
    if score_result.label is not None:
        headline = score_result.label

    any_proxy = any(
        (spec := get_kpi_spec(ministry.code, kpi.name)) is not None and spec.proxy_based
        for kpi in ministry.kpis
    )
    if any_proxy and not proxy_disclosure:
        # Safeguard #2 enforcement: never let a proxy-based insight ship silently.
        proxy_specs = [s for k in ministry.kpis if (s := get_kpi_spec(ministry.code, k.name)) and s.proxy_based]
        names = ", ".join(s.name for s in proxy_specs)
        proxy_disclosure = (
            f"This assessment relies in part on best-available proxy metrics ({names}) because no "
            "single official, directly-measured series exists for what they approximate."
        )

    return {
        "bullets": evidence,
        "inference": f"{headline} — {forward_implications}".strip(" —"),
        "headline": headline,
        "time_period_judged": time_period_judged,
        "caveats": caveats,
        "proxy_disclosure": proxy_disclosure,
        "data_quality_flag": data_quality_notes if data_quality_notes in ("HIGH", "MEDIUM", "LOW") else "MEDIUM",
        "comparative_context": comparative_context,
        "forward_implications": forward_implications,
    }


def _format_ministry_roster(ministries: list[Ministry]) -> str:
    lines = []
    for m in ministries:
        score = f"{m.score:.1f}" if m.score is not None else "n/a"
        lines.append(f"- {m.name} ({m.code}): score={score}/100, status={m.status}")
    return "\n".join(lines)


def chat_reply(
    message: str,
    history: list,
    ministry: Ministry | None,
    all_ministries: list[Ministry],
) -> str:
    if not settings.anthropic_api_key:
        raise HTTPException(
            status_code=503,
            detail="ANTHROPIC_API_KEY is not configured on the server.",
        )

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    if ministry is not None:
        framework = get_framework(ministry.code)
        framework_block = format_framework_for_prompt(framework) if framework else ""
        context = (
            f"The user is currently viewing the {ministry.name} ({ministry.code}) detail page.\n"
            f"Description: {ministry.description}\n\n"
            f"KPI data for this ministry:\n{_format_kpi_block(ministry.kpis, ministry.code)}\n\n"
            f"Analytical framework for this ministry:\n{framework_block}\n\n"
            f"All-ministry roster (for cross-ministry comparisons if asked):\n"
            f"{_format_ministry_roster(all_ministries)}"
        )
    else:
        context = (
            "The user is on the dashboard's overview/summary experience (no single ministry selected).\n\n"
            f"All-ministry roster:\n{_format_ministry_roster(all_ministries)}"
        )

    system_prompt = (
        "You are the AI assistant embedded in a government ministry performance dashboard. "
        "Answer questions ONLY using the KPI/roster/framework data provided in context below - do "
        "not invent figures that aren't present. If asked something the data can't answer, say so "
        "plainly and suggest what the user could check instead. Keep replies concise (2-5 "
        "sentences unless the user asks for detail), factual, and analytical in tone. When a KPI "
        "is marked [PROXY METRIC] in the context, say so if you cite it. "
        f"{DEMO_DATA_DISCLOSURE}\n\n"
        f"Context:\n{context}"
    )

    messages = [{"role": h.role, "content": h.content} for h in history if h.role in ("user", "assistant")]
    messages.append({"role": "user", "content": message})

    try:
        response = client.messages.create(
            model=CHAT_MODEL,
            max_tokens=512,
            output_config={"effort": "low"},
            system=system_prompt,
            messages=messages,
        )
    except anthropic.AuthenticationError:
        raise HTTPException(status_code=502, detail="Invalid Anthropic API key.")
    except anthropic.RateLimitError:
        raise HTTPException(status_code=429, detail="Claude API rate limit hit, try again shortly.")
    except anthropic.APIStatusError as e:
        raise HTTPException(status_code=502, detail=f"Claude API error: {e.message}")

    return "".join(block.text for block in response.content if block.type == "text").strip()


def get_or_generate_insights(
    db: Session, ministry: Ministry, force: bool = False
) -> tuple[MinistryInsight, bool]:
    """Return the ministry's cached briefing if its KPI values haven't
    changed since it was generated; otherwise call Claude and cache the
    fresh result. Returns (insight, was_cache_hit)."""
    current_hash = _kpi_snapshot_hash(ministry.kpis)
    cached = ministry.insight

    if cached is not None and not force and cached.kpi_snapshot_hash == current_hash:
        return cached, True

    result = _call_claude(ministry)

    if cached is None:
        cached = MinistryInsight(ministry_id=ministry.id)
        db.add(cached)

    cached.bullets = result["bullets"]
    cached.inference = result["inference"]
    cached.kpi_snapshot_hash = current_hash
    cached.generated_at = datetime.now(timezone.utc)
    cached.headline = result["headline"]
    cached.time_period_judged = result["time_period_judged"]
    cached.caveats = result["caveats"]
    cached.proxy_disclosure = result["proxy_disclosure"]
    cached.data_quality_flag = result["data_quality_flag"]
    cached.comparative_context = result["comparative_context"]
    cached.forward_implications = result["forward_implications"]
    cached.framework_version = "1.0"
    db.commit()
    db.refresh(cached)
    return cached, False
