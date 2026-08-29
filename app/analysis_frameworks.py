"""Ministry-level analytical frameworks used to judge "Good / Mediocre / Poor"
performance. This is the rubric Claude (both the per-ministry insights engine
in app/claude_service.py and the Tarka chatbot in app/tarka_chatbot.py) is
required to reason from, instead of freelancing a verdict from raw numbers.

Each framework gives good/mediocre/poor criteria, standing caveats that must
be surfaced whenever the framework is used, and comparative context (targets,
historical baselines, peer benchmarks) so verdicts aren't judged in a vacuum.
"""

from __future__ import annotations

CORE_ANALYTICAL_PRINCIPLES = [
    "Judge by outcomes affecting productivity, competitiveness, employment, fiscal "
    "sustainability, and strategic capacity — not by activity or spending alone.",
    "Distinguish cyclical movements (global commodity swings, base effects, one-off "
    "receipts) from structural ones (genuine capacity, productivity, or institutional change).",
    "Explicitly flag data limitations and proxy status; never present a proxy as a "
    "definitive official metric.",
    "Prefer multi-year trends over single-year snapshots.",
    "Be willing to call performance Good, Mediocre, or Poor with clear justification — "
    "don't default to noncommittal hedging.",
    "Never oversimplify; surface trade-offs and second-order effects.",
    "Always state the time period being judged.",
]


FINANCE_FRAMEWORK = {
    "ministry_code": "FIN",
    "good_criteria": [
        "Fiscal deficit on a credible declining path toward 4.5% of GDP or lower.",
        "Tax-to-GDP rising structurally, not just due to nominal growth.",
        "Tax administration showing declining coercive intensity.",
        "Capital expenditure quality maintained despite consolidation.",
    ],
    "mediocre_criteria": [
        "Deficit consolidation mainly through revenue buoyancy rather than expenditure discipline.",
        "Tax-harassment indicators remain elevated despite higher collections.",
        "Quality of adjustment weak (heavy reliance on cesses, postponed payments).",
    ],
    "poor_criteria": [
        "Deficit remains sticky at high levels with no credible glide path.",
        "Quality of adjustment weak (cuts fall on human capital / defence capex).",
        "Tax administration becomes more extractive and unpredictable.",
    ],
    "caveats": [
        "High nominal GDP growth mechanically lowers deficit ratios — check real consolidation.",
        "Off-budget items and state-level deficits can mask true fiscal stress.",
        "One-off spectrum/disinvestment receipts inflate temporary performance.",
        "Tax harassment is hard to quantify precisely; use available proxies and say so.",
    ],
    "comparative_context": {
        "historical_target": "4.5% by 2025-26 (pre-COVID FRBM glide path)",
        "upa_era_average": "4.5-5.5% (2009-14)",
        "global_peers": "Advanced economies typically 2-3%, emerging markets 4-6%",
    },
}

PETROLEUM_FRAMEWORK = {
    "ministry_code": "PETRO",
    "good_criteria": [
        "Import dependence stable or falling despite rising domestic demand.",
        "Ethanol blending targets met or exceeded without straining food-grain supply.",
        "LPG coverage sustained with rising refill/usage rates, not just connection counts.",
    ],
    "mediocre_criteria": [
        "Import dependence flat while domestic exploration investment stalls.",
        "Blending targets met on paper but with regional supply bottlenecks.",
    ],
    "poor_criteria": [
        "Import dependence rising with no credible domestic production or diversification plan.",
        "LPG connections issued but refill rates stagnant (indicating non-adoption).",
    ],
    "caveats": [
        "Global crude price swings dominate short-run import-dependence numbers — separate "
        "price effect from volume effect.",
        "Ethanol feedstock sourcing has a food-security trade-off not captured by the blending % alone.",
    ],
    "comparative_context": {
        "ethanol_target": "20% blending (E20) national target",
        "historical_import_dependence": "~75-88% range over the last decade",
    },
}

AGRICULTURE_FRAMEWORK = {
    "ministry_code": "AGRI",
    "good_criteria": [
        "Real farmer income rising, not just nominal agricultural GVA.",
        "Food inflation contained without price-support programmes collapsing farmgate prices.",
        "Credit disbursement growth reaching actual cultivators, not concentrated in large-holding segments.",
    ],
    "mediocre_criteria": [
        "Nominal income rising but real income roughly flat after CPI deflation.",
        "Food inflation volatile, swinging between shortage-driven spikes and glut-driven crashes.",
    ],
    "poor_criteria": [
        "Real farmer income stagnant or declining over a multi-year window.",
        "Food inflation persistently high, eroding urban and rural real wages alike.",
    ],
    "caveats": [
        "Direct farmer income surveys are infrequent — most annual estimates are model-based, "
        "not measured.",
        "Aggregate income/GVA figures mask large disparities between smallholders and large farms.",
        "Weather/monsoon shocks dominate single-year food-inflation readings.",
    ],
    "comparative_context": {
        "policy_target": "Doubling farmer income (2016 target, base year 2015-16)",
    },
}

RAILWAYS_FRAMEWORK = {
    "ministry_code": "RAIL",
    "good_criteria": [
        "Freight volume (MT and NTKM) growing ahead of GDP growth, indicating modal share gains.",
        "Passenger traffic recovered and growing post-COVID.",
        "On-time performance improving on a consistent measurement basis.",
    ],
    "mediocre_criteria": [
        "Freight growth roughly tracking GDP with no modal-share gain versus road transport.",
        "On-time performance improving only due to a looser definition change.",
    ],
    "poor_criteria": [
        "Freight volume growth lagging GDP, indicating share loss to road/other modes.",
        "Passenger or safety metrics deteriorating.",
    ],
    "caveats": [
        "COVID-year figures (FY2020-21 especially) are structural outliers — always compare "
        "against a pre-COVID baseline, not the COVID trough.",
        "On-time performance methodology has changed across report years.",
    ],
    "comparative_context": {
        "modal_share_context": "Rail's freight modal share has structurally declined against road "
        "since the 1990s; a 'good' reading requires reversing that trend, not just posting growth.",
    },
}

POWER_FRAMEWORK = {
    "ministry_code": "POW",
    "good_criteria": [
        "AT&C losses on a sustained declining path across most states, not just the national average.",
        "Renewable capacity growth translating into actual generation share gains, not only nameplate capacity.",
        "Per capita consumption rising broadly across income groups, indicating access gains.",
    ],
    "mediocre_criteria": [
        "National AT&C average improves while a large minority of states stagnate or worsen.",
        "Renewable capacity added but curtailment/grid-integration issues limit real generation share.",
    ],
    "poor_criteria": [
        "AT&C losses flat or rising, indicating unresolved distribution-utility financial stress.",
        "Renewable capacity growth is mostly a headline number with limited grid impact.",
    ],
    "caveats": [
        "AT&C loss definitional methodology has changed across PFC report editions.",
        "Capacity growth != generation growth; check capacity utilisation factors.",
        "National averages hide extreme state-level dispersion in distribution utility health.",
    ],
    "comparative_context": {
        "atc_target": "12-15% AT&C losses (UDAY scheme target band)",
    },
}

COMMERCE_FRAMEWORK = {
    "ministry_code": "COMM",
    "good_criteria": [
        "Merchandise export growth outpacing global trade growth (market-share gain).",
        "FDI inflows diversified across sectors, not concentrated in one or two booms.",
        "Import dependence on strategic industrial inputs declining over time.",
    ],
    "mediocre_criteria": [
        "Export growth roughly tracking global trade growth (no share gain, no share loss).",
        "FDI inflows strong in headline terms but concentrated in low-multiplier sectors.",
    ],
    "poor_criteria": [
        "Export growth lagging global trade growth (share loss).",
        "Import dependence on critical inputs rising with no diversification plan.",
    ],
    "caveats": [
        "USD-denominated trade figures conflate volume, price, and exchange-rate effects.",
        "Gross FDI figures don't net out repatriation; treaty round-tripping can inflate the headline.",
        "Ease-of-Doing-Business index was discontinued by the World Bank in 2021 due to data "
        "integrity issues — any pre/post comparison using it is unreliable.",
    ],
    "comparative_context": {},
}

DEFENCE_FRAMEWORK = {
    "ministry_code": "DEF",
    "good_criteria": [
        "Genuine design/IP indigenisation rising (not just domestic assembly of licensed foreign designs).",
        "Defence exports growing off a credible, diversified product base.",
        "Border infrastructure completed to all-weather, year-round usable standard.",
    ],
    "mediocre_criteria": [
        "Procurement value indigenisation rising mostly via licensed/assembled production.",
        "Export growth concentrated in a narrow product range or a small number of buyers.",
    ],
    "poor_criteria": [
        "Claimed indigenisation gains not corroborated by independent design-capability evidence.",
        "Border infrastructure completion figures include roads not usable year-round.",
    ],
    "caveats": [
        "Official indigenisation percentages are self-reported and not independently audited — "
        "treat as a claim, not a verified fact, and say so explicitly.",
        "Export growth off a very low base can produce large but not meaningful % figures.",
    ],
    "comparative_context": {},
}

EDUCATION_FRAMEWORK = {
    "ministry_code": "EDU",
    "good_criteria": [
        "ASER foundational learning outcomes improving across successive survey rounds.",
        "Gross Enrolment Ratio rising alongside stable or improving pupil-teacher ratios.",
        "Improvements consistent across rural and urban, not concentrated in urban areas alone.",
    ],
    "mediocre_criteria": [
        "Enrolment rising while learning outcomes stagnate (access without quality gain).",
        "Pupil-teacher ratio improving nationally while masking large state-level gaps.",
    ],
    "poor_criteria": [
        "ASER learning outcomes flat or declining across survey rounds.",
        "Enrolment growth not matched by teacher hiring, worsening effective classroom ratios.",
    ],
    "caveats": [
        "ASER covers rural India only — do not generalise to national/urban outcomes.",
        "GER measures access, not completion or learning quality.",
        "COVID-era school closures created a multi-year learning-loss disruption that needs its "
        "own caveat when comparing pre/post periods.",
    ],
    "comparative_context": {},
}

SKILL_DEVELOPMENT_FRAMEWORK = {
    "ministry_code": "SKILL",
    "good_criteria": [
        "Unemployment rate declining on a consistent (post-PLFS) measurement basis.",
        "PMKVY-trained youth showing improving post-training placement rates, not just training counts.",
        "Formal-sector job proxies (EPFO net additions) growing net of formalisation-only effects.",
    ],
    "mediocre_criteria": [
        "Training counts rising while placement/wage outcomes are not reported or are weak.",
        "EPFO net additions rising but largely explained by existing-employer formalisation.",
    ],
    "poor_criteria": [
        "Unemployment rate rising or persistently high across multiple PLFS rounds.",
        "Training program throughput high but disconnected from actual labour-market demand.",
    ],
    "caveats": [
        "Pre-FY2017-18 unemployment data uses a different survey methodology (NSSO) — not "
        "comparable to PLFS-era figures.",
        "EPFO net subscriber additions are a PROXY for job creation, not a direct count of new jobs.",
    ],
    "comparative_context": {},
}

ROAD_TRANSPORT_FRAMEWORK = {
    "ministry_code": "ROAD",
    "good_criteria": [
        "Highway construction pace sustained or rising with genuinely new construction (not just reclassification).",
        "Road accident fatality RATE (per vehicle-km) declining, even if absolute deaths are flat "
        "due to rising vehicle population.",
    ],
    "mediocre_criteria": [
        "Construction pace strong but safety metrics not improving in tandem.",
        "Network length growing significantly via state-highway reclassification rather than new builds.",
    ],
    "poor_criteria": [
        "Construction pace declining and road accident fatalities rising in absolute terms.",
    ],
    "caveats": [
        "Network-length growth includes reclassification of existing state highways, not solely new "
        "construction.",
        "Absolute fatality counts should be read alongside a rate metric (per vehicle-km or per "
        "1,000 registered vehicles) since the vehicle population is also growing.",
    ],
    "comparative_context": {},
}

FRAMEWORKS: dict[str, dict] = {
    "FIN": FINANCE_FRAMEWORK,
    "PETRO": PETROLEUM_FRAMEWORK,
    "AGRI": AGRICULTURE_FRAMEWORK,
    "RAIL": RAILWAYS_FRAMEWORK,
    "POW": POWER_FRAMEWORK,
    "COMM": COMMERCE_FRAMEWORK,
    "DEF": DEFENCE_FRAMEWORK,
    "EDU": EDUCATION_FRAMEWORK,
    "SKILL": SKILL_DEVELOPMENT_FRAMEWORK,
    "ROAD": ROAD_TRANSPORT_FRAMEWORK,
}

assert len(FRAMEWORKS) == 10, f"expected 10 ministry frameworks, got {len(FRAMEWORKS)}"


def get_framework(ministry_code: str) -> dict | None:
    return FRAMEWORKS.get(ministry_code)


def format_framework_for_prompt(framework: dict) -> str:
    """Render a framework dict into a compact text block for a Claude system prompt."""
    lines = [
        "GOOD performance means:",
        *[f"  - {c}" for c in framework["good_criteria"]],
        "MEDIOCRE performance means:",
        *[f"  - {c}" for c in framework["mediocre_criteria"]],
        "POOR performance means:",
        *[f"  - {c}" for c in framework["poor_criteria"]],
        "Standing caveats for this ministry (surface at least one relevant one):",
        *[f"  - {c}" for c in framework["caveats"]],
    ]
    if framework.get("comparative_context"):
        lines.append("Comparative context:")
        lines += [f"  - {k}: {v}" for k, v in framework["comparative_context"].items()]
    return "\n".join(lines)
