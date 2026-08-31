"""Tarka: the analytical policy chatbot for the ministry dashboard.

Tarka answers questions using the same rubric as the cached per-ministry
insights (app/claude_service.py) — the analysis frameworks in
app/analysis_frameworks.py and the KPI safeguards in
app/kpi_specifications.py — but conversationally, and across ministries.

Behavior rules (enforced via the system prompt below):
  - "Is X good?" is answered through the framework, never a bare yes/no.
  - Proxy-based data is always explicitly disclosed as a proxy.
  - Answers encourage multi-KPI thinking rather than single-number verdicts.
  - Tarka is analytically independent: it does not defend or attack any
    government, only the data and the framework.
  - Every answer states the time period being judged.
"""

from __future__ import annotations

import json

import anthropic
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.analysis_frameworks import CORE_ANALYTICAL_PRINCIPLES, format_framework_for_prompt, get_framework
from app.claude_service import DEMO_DATA_DISCLOSURE, _format_kpi_block, _score_block
from app.config import settings
from app.kpi_specifications import get_kpi_spec, get_specs_for_ministry
from app.models import Ministry

MODEL = "claude-sonnet-5"

TARKA_SYSTEM_PREAMBLE = (
    "You are Tarka, a senior Indian macroeconomic analyst and analytical policy chatbot. You "
    "evaluate ministry performance using a transparent, weighted KPI scoring system (0-100) that "
    "prioritises structural outcomes over optics. Where a ministry's composite score and KPI "
    "breakdown are given to you in context, they are computed deterministically by the app — "
    "treat them as ground truth, do not recompute or contradict them.\n\n"
    "You embody rigorous macroeconomic analysis and these principles:\n\n"
    f"{chr(10).join(f'{i}. {p}' for i, p in enumerate(CORE_ANALYTICAL_PRINCIPLES, 1))}\n\n"
    "Behavior rules:\n"
    "- When asked 'How is Ministry X performing?' or 'Is X good?', FIRST give the composite score "
    "and label (Strong / Satisfactory / Mediocre / Weak / Poor), THEN the KPI-by-KPI breakdown — "
    "never a bare yes/no.\n"
    "- Break down the contribution of each KPI: name, weight, and how its data quality affected "
    "its effective weight.\n"
    "- When data is proxy-based or incomplete, explicitly say its effective weight was reduced, not "
    "just that it's a proxy.\n"
    "- Distinguish cyclical noise (commodity swings, base effects, one-off receipts) from structural "
    "trends (genuine capacity/productivity/institutional change).\n"
    "- Compare against both the official target and the aspirational/structural target.\n"
    "- Never treat equal weights as default — respect the economic-importance weights given in context.\n"
    "- Offer to show the exact formula and assumptions behind a score if it would help the user.\n"
    "- If the user challenges a weight or target, explain the economic rationale transparently — "
    "don't just defer or restate the number.\n"
    "- Encourage looking at multiple years and related ministries together.\n"
    "- Encourage multi-KPI thinking generally.\n"
    "- Maintain analytical independence (don't defend/attack any government).\n"
    "- Always state the time period you are judging.\n\n"
    f"{DEMO_DATA_DISCLOSURE}"
)

_ANSWER_JSON_CONTRACT = (
    'Respond with ONLY a JSON object (no markdown fences) with exactly this shape:\n'
    "{\n"
    '  "headline": "...",\n'
    '  "evidence": ["...", "...", "..."],\n'
    '  "caveats": ["...", "..."],\n'
    '  "comparative_context": "...",\n'
    '  "forward_implications": "...",\n'
    '  "time_period_judged": "...",\n'
    '  "data_quality_flag": "HIGH" | "MEDIUM" | "LOW",\n'
    '  "proxy_disclosure": "..." or null\n'
    "}\n"
    "evidence must have 2-4 items grounded in the data given; caveats must have at least 1 item; "
    "time_period_judged must be a concrete period, never bare 'recent'/'current'."
)


def _client() -> anthropic.Anthropic:
    if not settings.anthropic_api_key:
        raise HTTPException(status_code=503, detail="ANTHROPIC_API_KEY is not configured on the server.")
    return anthropic.Anthropic(api_key=settings.anthropic_api_key)


def _ask_structured(system_prompt: str, user_prompt: str) -> dict:
    client = _client()

    # One retry on a malformed/truncated response — LLM structured output is occasionally
    # flaky independent of the token-budget fix below; a single retry clears most of these
    # without the user needing to click "Ask" again.
    last_error = "Tarka returned an unexpected response format."
    for attempt in range(2):
        try:
            response = client.messages.create(
                model=MODEL,
                # Same headroom fix as claude_service._call_claude — the score-breakdown /
                # cyclical-vs-structural / dual-target instructions produce longer responses
                # than 1024 tokens reliably covers, causing truncated (unterminated) JSON.
                max_tokens=2200,
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
        except json.JSONDecodeError:
            last_error = "Tarka returned an unexpected response format."
            continue

        data.setdefault("evidence", [])
        data.setdefault("caveats", [])
        data.setdefault("comparative_context", "")
        data.setdefault("forward_implications", "")
        data.setdefault("time_period_judged", "")
        data.setdefault("data_quality_flag", "MEDIUM")
        data.setdefault("proxy_disclosure", None)
        data.setdefault("headline", "")
        if not data["caveats"]:
            last_error = "Tarka did not return any caveats."
            continue

        return data

    raise HTTPException(status_code=502, detail=f"{last_error} (retried once)")


def _ministry_context_block(ministry: Ministry) -> str:
    framework = get_framework(ministry.code)
    framework_block = format_framework_for_prompt(framework) if framework else "(no framework on file)"
    return (
        f"Ministry: {ministry.name} ({ministry.code})\n"
        f"Description: {ministry.description}\n\n"
        f"Ministry Performance Score (computed by the app, not by you):\n{_score_block(ministry)}\n\n"
        f"KPI data:\n{_format_kpi_block(ministry.kpis, ministry.code)}\n\n"
        f"Analytical framework:\n{framework_block}"
    )


def _with_deterministic_headline(result: dict, ministry: Ministry) -> dict:
    """Override Claude's freeform headline with the app-computed score label,
    so a single-ministry verdict never disagrees with the score shown
    elsewhere in the dashboard."""
    label = ministry.score_label
    if label is not None:
        result["headline"] = label
    return result


def answer_performance_question(ministry: Ministry, question: str) -> dict:
    """'Is Finance performing well?' -> framework-grounded structured answer."""
    system_prompt = f"{TARKA_SYSTEM_PREAMBLE}\n\n{_ANSWER_JSON_CONTRACT}"
    user_prompt = (
        f"{_ministry_context_block(ministry)}\n\n"
        f"User question: {question}\n\n"
        "Answer using Headline | Evidence | Caveats | Context | Implications structure, "
        "reflected in the required JSON fields. If the question is a general performance "
        "judgment, lead 'evidence' with the composite score and its largest weighted driver."
    )
    return _with_deterministic_headline(_ask_structured(system_prompt, user_prompt), ministry)


def compare_ministries(ministry_1: Ministry, ministry_2: Ministry, aspect: str = "") -> dict:
    """Comparative analysis between two ministries, optionally on a named aspect
    (e.g. 'fiscal discipline', 'infrastructure delivery pace')."""
    system_prompt = f"{TARKA_SYSTEM_PREAMBLE}\n\n{_ANSWER_JSON_CONTRACT}"
    aspect_line = f"Focus the comparison on: {aspect}\n\n" if aspect else ""
    user_prompt = (
        f"=== {ministry_1.name} ({ministry_1.code}) ===\n{_ministry_context_block(ministry_1)}\n\n"
        f"=== {ministry_2.name} ({ministry_2.code}) ===\n{_ministry_context_block(ministry_2)}\n\n"
        f"{aspect_line}"
        f"Compare these two ministries' performance using their composite scores above as the "
        "primary basis. 'headline' should name which one comes out ahead (or 'Mixed' if genuinely "
        "not comparable — e.g. very different mandates), citing both composite scores; 'evidence' "
        "should cite specific KPIs from both sides, not just the top-line scores."
    )
    return _ask_structured(system_prompt, user_prompt)


def explain_kpi(kpi_name: str, ministry: Ministry) -> dict:
    """What this metric means, why it matters, and its caveats — grounded in
    the KPI's spec from app.kpi_specifications, not freeform."""
    spec = get_kpi_spec(ministry.code, kpi_name)
    if spec is None:
        return {
            "headline": kpi_name,
            "evidence": [],
            "caveats": [f"No documented specification found for '{kpi_name}' under {ministry.name}."],
            "comparative_context": "",
            "forward_implications": "",
            "time_period_judged": "",
            "data_quality_flag": "LOW",
            "proxy_disclosure": None,
        }

    proxy_disclosure = None
    if spec.proxy_based:
        proxy_disclosure = (
            f"'{spec.name}' is a best available proxy for {spec.definition.split(':')[0].strip()} "
            f"because no single official, directly-measured series exists — it is assembled from: "
            f"{', '.join(spec.data_points)}."
        )

    return {
        "headline": spec.name,
        "evidence": [
            f"Definition: {spec.definition}",
            f"Calculation: {spec.calculation}" + (f" (formula: {spec.formula})" if spec.formula else ""),
            f"Source: {spec.source_name} ({spec.source_url}), updated {spec.update_frequency}.",
        ],
        "caveats": list(spec.caveats),
        "comparative_context": f"Units: {spec.units}. Time period tracked: {spec.time_period}. "
        f"Build tier: {spec.tier} ({'high-confidence, build first' if spec.tier == 'A' else 'secondary' if spec.tier == 'B' else 'deferred, explicit proxy'}).",
        "forward_implications": "",
        "time_period_judged": spec.time_period,
        "data_quality_flag": spec.data_quality,
        "proxy_disclosure": proxy_disclosure,
    }


def generate_trend_analysis(ministry: Ministry, time_period: str = "") -> dict:
    """Cyclical vs. structural read of the ministry's KPI trends."""
    system_prompt = f"{TARKA_SYSTEM_PREAMBLE}\n\n{_ANSWER_JSON_CONTRACT}"
    period_line = f"Focus specifically on the period: {time_period}\n\n" if time_period else ""
    user_prompt = (
        f"{_ministry_context_block(ministry)}\n\n"
        f"{period_line}"
        "Generate a trend analysis: for each notable KPI movement, classify it as CYCLICAL "
        "(commodity swings, base effects, one-off receipts) or STRUCTURAL (genuine capacity/"
        "productivity/institutional change), and explain why. Note whether the trend adjustment "
        "already folded into the composite score (given above) matches your read. Put the "
        "classification and reasoning in 'evidence'; state which period you're judging in "
        "'time_period_judged'."
    )
    return _with_deterministic_headline(_ask_structured(system_prompt, user_prompt), ministry)


def suggest_focus_areas(ministry: Ministry) -> dict:
    """What metrics/areas matter most for this ministry right now, and why."""
    specs = get_specs_for_ministry(ministry.code)
    tier_a = [s.name for s in specs if s.tier == "A"]
    tier_c = [s.name for s in specs if s.tier == "C"]

    system_prompt = f"{TARKA_SYSTEM_PREAMBLE}\n\n{_ANSWER_JSON_CONTRACT}"
    user_prompt = (
        f"{_ministry_context_block(ministry)}\n\n"
        f"High-confidence (Tier A) KPIs on file: {', '.join(tier_a) or 'none'}\n"
        f"Deferred/proxy (Tier C) KPIs on file: {', '.join(tier_c) or 'none'}\n\n"
        "Suggest the 2-4 focus areas that matter most for judging this ministry going forward, "
        "and why (put these in 'evidence'). Prefer high-confidence data sources over low-quality "
        "proxies when recommending what a decision-maker should actually track."
    )
    return _ask_structured(system_prompt, user_prompt)
