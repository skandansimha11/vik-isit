"""Seeds the 10 ministries required by the dashboard spec, each with exactly
3 KPIs (hero + 2 others) carrying curated FY2014-15..FY2025-26 analytics
series so every chart type in the spec has real data to render.

This is additive/idempotent: matches ministries by code and KPIs by name, so
re-running it is safe. It does NOT touch the live connector demo wired up
for Finance's "Fiscal Deficit" KPI (app/connectors/ministries/finance.yaml +
app/pipeline) other than updating its display metadata - its current_value
stays live-sync-able via POST /sync.

Run with:
    python -m app.seed_dashboard
"""

from __future__ import annotations

import random
from datetime import datetime, timezone

from app.database import Base, SessionLocal, engine, sync_schema
from app.models import KPI, Event, KPISeriesPoint, Ministry

YEARS = list(range(2014, 2026))  # 12 points: FY2014-15 .. FY2025-26


def period_label(year: int) -> str:
    return f"FY{str(year + 1)[2:]}"


def lerp(start: float, end: float, jitter: float = 0.0, seed: int = 0, curve: str = "linear") -> list[float]:
    n = len(YEARS)
    rng = random.Random(seed)
    out = []
    for i in range(n):
        t = i / (n - 1)
        if curve == "ease_out":
            t = 1 - (1 - t) ** 2
        elif curve == "ease_in":
            t = t ** 2
        val = start + (end - start) * t
        if jitter:
            val += rng.uniform(-jitter, jitter)
        out.append(round(val, 2))
    out[0] = round(start, 2)
    out[-1] = round(end, 2)
    return out


def set_year(arr: list[float], year: int, val: float) -> list[float]:
    arr[year - 2014] = round(val, 2)
    return arr


def complement(arr: list[float], total: float = 100.0) -> list[float]:
    return [round(total - v, 2) for v in arr]


def time_line_series(values: list[float], targets: list[float] | float | None = None) -> list[dict]:
    rows = []
    for i, y in enumerate(YEARS):
        t = targets[i] if isinstance(targets, list) else targets
        rows.append({"year": y, "period_label": period_label(y), "value": values[i], "target_value": t})
    return rows


def time_dual_series(values: list[float], secondary: list[float]) -> list[dict]:
    return [
        {"year": y, "period_label": period_label(y), "value": values[i], "secondary_value": secondary[i]}
        for i, y in enumerate(YEARS)
    ]


def time_breakdown_series(series_map: dict[str, list[float]]) -> list[dict]:
    rows = []
    for i, y in enumerate(YEARS):
        breakdown = {k: v[i] for k, v in series_map.items()}
        rows.append(
            {
                "year": y,
                "period_label": period_label(y),
                "value": round(sum(breakdown.values()) / len(breakdown), 2),
                "breakdown": breakdown,
            }
        )
    return rows


def category_series(breakdown: dict, current_keys: tuple[str, ...] | None = None) -> list[dict]:
    y = YEARS[-1]
    vals: list[float] = []
    for v in breakdown.values():
        if isinstance(v, dict):
            picked = False
            if current_keys:
                for ck in current_keys:
                    if ck in v:
                        vals.append(v[ck])
                        picked = True
                        break
            if not picked:
                vals.extend(v.values())
        else:
            vals.append(v)
    avg = round(sum(vals) / len(vals), 2) if vals else 0.0
    return [{"year": y, "period_label": period_label(y), "value": avg, "breakdown": breakdown}]


# --------------------------------------------------------------------------
# Ministry + KPI definitions
# --------------------------------------------------------------------------

fiscal_deficit = lerp(6.6, 4.7, jitter=0.1, seed=1)
set_year(fiscal_deficit, 2019, 4.6)
set_year(fiscal_deficit, 2020, 9.2)
set_year(fiscal_deficit, 2021, 6.7)
set_year(fiscal_deficit, 2022, 6.4)
set_year(fiscal_deficit, 2023, 5.9)
set_year(fiscal_deficit, 2024, 5.6)
fiscal_deficit_target = lerp(4.9, 4.5, jitter=0, seed=2)

tax_growth = lerp(9.5, 11.8, jitter=0.5, seed=3)
set_year(tax_growth, 2020, -3.4)
set_year(tax_growth, 2021, 16.8)
gdp_growth = lerp(7.0, 6.8, jitter=0.3, seed=4)
set_year(gdp_growth, 2020, -5.8)
set_year(gdp_growth, 2021, 9.7)

industrial_imports = lerp(38.5, 31.2, jitter=0.4, seed=5)
mfg_growth = lerp(6.8, 9.4, jitter=0.6, seed=6)
set_year(mfg_growth, 2020, -8.0)
set_year(mfg_growth, 2021, 11.2)
mfg_output = lerp(24.5, 46.2, jitter=0.4, seed=7)

freight_growth = lerp(4.2, 8.6, jitter=0.5, seed=8)
set_year(freight_growth, 2020, -20.8)
set_year(freight_growth, 2021, 15.4)
freight_target = lerp(6.0, 9.0, jitter=0, seed=0)

rail_share = lerp(36.0, 32.0, jitter=0.4, seed=9)
set_year(rail_share, 2020, 30.5)
road_share = complement(rail_share)

tariff_mh = lerp(7.8, 8.6, jitter=0.15, seed=10)
tariff_gj = lerp(6.9, 7.4, jitter=0.15, seed=11)
tariff_tn = lerp(7.2, 8.1, jitter=0.15, seed=12)
tariff_up = lerp(7.5, 8.3, jitter=0.15, seed=13)

discom_losses = lerp(65.0, 48.0, jitter=2.5, seed=14)
atc_losses = lerp(21.4, 15.2, jitter=0.4, seed=15)

power_availability = lerp(94.2, 99.6, jitter=0.25, seed=16)

defence_capex = lerp(1.55, 1.85, jitter=0.04, seed=17)
defence_capex_benchmark = [1.6] * len(YEARS)

neet_rate = lerp(30.2, 22.4, jitter=0.5, seed=18)
set_year(neet_rate, 2020, 33.1)
set_year(neet_rate, 2021, 29.8)
neet_baseline = [30.2] * len(YEARS)

apprentice_budget = lerp(2800, 7800, jitter=90, seed=19)
apprentice_actual = lerp(1400, 5600, jitter=120, seed=20)

jobs_created = lerp(21.4, 89.6, jitter=2.5, seed=21)
set_year(jobs_created, 2020, -12.0)
set_year(jobs_created, 2021, 41.2)

farmer_income = lerp(100.0, 148.0, jitter=1.5, seed=22)

ethanol_volume = lerp(38.0, 720.0, jitter=12, seed=23, curve="ease_out")
ethanol_forex = lerp(0.30, 1.02, jitter=0.03, seed=24, curve="ease_out")

food_inflation = lerp(6.4, 7.8, jitter=0.6, seed=25)
set_year(food_inflation, 2020, 9.1)
set_year(food_inflation, 2022, 6.7)

oil_dependence = lerp(81.0, 87.7, jitter=0.4, seed=26)
ethanol_blend = lerp(1.5, 15.8, jitter=0.3, seed=27, curve="ease_out")

refining_throughput = lerp(221.0, 268.0, jitter=2.5, seed=28)
refining_cost = lerp(3.1, 4.4, jitter=0.1, seed=29)

logistics_cost = lerp(14.4, 8.9, jitter=0.25, seed=30)

highway_pace = lerp(12.1, 28.3, jitter=1.2, seed=31)

modal_road = lerp(58.0, 66.0, jitter=0.5, seed=32)
modal_rail = lerp(36.0, 27.0, jitter=0.5, seed=33)
modal_multi = [round(100 - r - l, 2) for r, l in zip(modal_road, modal_rail)]


MINISTRIES: list[dict] = [
    {
        "code": "FIN",
        "name": "Ministry of Finance",
        "description": "Responsible for fiscal policy, the union budget, taxation, and public expenditure.",
        "kpis": [
            {
                "name": "Fiscal Deficit",
                "category": "fiscal performance",
                "unit": "% of GDP",
                "target_value": 4.5,
                "period": "FY 2025-26",
                "chart_type": "line",
                "data_shape": "time_line",
                "hero": True,
                "higher_is_better": False,
                "benchmark_label": "Official Glide-Path Target",
                "series": time_line_series(fiscal_deficit, fiscal_deficit_target),
            },
            {
                "name": "Tax Harassment Cases",
                "category": "taxpayer services",
                "unit": "'000 cases",
                "target_value": 252.5,
                "period": "FY 2025-26",
                "chart_type": "grouped_bar",
                "data_shape": "category_compare",
                "higher_is_better": False,
                "breakdown_label": "Category",
                "benchmark_label": "Target",
                "series": category_series(
                    {
                        "Scrutiny Notices": {"current": 812, "target": 600},
                        "Reassessment >6yr": {"current": 143, "target": 60},
                        "Faceless Appeals Pending": {"current": 549, "target": 300},
                        "Taxpayer Grievances": {"current": 96, "target": 50},
                    },
                    current_keys=("current",),
                ),
            },
            {
                "name": "Tax Collection Growth",
                "category": "revenue",
                "unit": "% YoY",
                "target_value": 12.0,
                "period": "FY 2025-26",
                "chart_type": "dual_axis",
                "data_shape": "time_dual",
                "higher_is_better": True,
                "secondary_label": "Nominal GDP Growth",
                "secondary_unit": "%",
                "series": time_dual_series(tax_growth, gdp_growth),
            },
        ],
    },
    {
        "code": "COMM",
        "name": "Ministry of Commerce & Industry",
        "description": "Responsible for trade policy, industrial promotion, and export competitiveness.",
        "kpis": [
            {
                "name": "Industrial Imports %",
                "category": "trade",
                "unit": "% of demand",
                "target_value": 26.0,
                "period": "FY 2025-26",
                "chart_type": "line",
                "data_shape": "time_line",
                "hero": True,
                "higher_is_better": False,
                "series": time_line_series(industrial_imports, 26.0),
            },
            {
                "name": "Manufacturing Growth",
                "category": "industrial output",
                "unit": "% YoY",
                "target_value": 10.0,
                "period": "FY 2025-26",
                "chart_type": "dual_axis",
                "data_shape": "time_dual",
                "higher_is_better": True,
                "secondary_label": "Manufacturing Output",
                "secondary_unit": "₹ Lakh Cr",
                "series": time_dual_series(mfg_growth, mfg_output),
            },
            {
                "name": "PLI Effectiveness",
                "category": "industrial policy",
                "unit": "% realised",
                "target_value": 80.0,
                "period": "FY 2025-26",
                "chart_type": "grouped_bar",
                "data_shape": "category_compare",
                "higher_is_better": True,
                "breakdown_label": "Sector",
                "benchmark_label": "Committed Target",
                "series": category_series(
                    {
                        "Electronics": {"current": 78, "target": 90},
                        "Pharma": {"current": 64, "target": 85},
                        "Textiles": {"current": 41, "target": 75},
                        "Auto & ACC": {"current": 57, "target": 80},
                        "Steel": {"current": 49, "target": 70},
                    },
                    current_keys=("current",),
                ),
            },
        ],
    },
    {
        "code": "RAIL",
        "name": "Ministry of Railways",
        "description": "Responsible for national rail infrastructure, passenger and freight operations, and rail safety.",
        "kpis": [
            {
                "name": "Freight Volume Growth",
                "category": "operations",
                "unit": "% YoY",
                "target_value": 9.0,
                "period": "FY 2025-26",
                "chart_type": "line",
                "data_shape": "time_line",
                "hero": True,
                "higher_is_better": True,
                "benchmark_label": "Annual Target",
                "series": time_line_series(freight_growth, freight_target),
            },
            {
                "name": "Rail Market Share",
                "category": "modal share",
                "unit": "% of freight",
                "target_value": 40.0,
                "period": "FY 2025-26",
                "chart_type": "stacked_area",
                "data_shape": "time_breakdown",
                "higher_is_better": True,
                "breakdown_label": "Mode",
                "series": time_breakdown_series({"Rail": rail_share, "Road": road_share}),
            },
            {
                "name": "Train Speeds & Capacity",
                "category": "service quality",
                "unit": "index",
                "target_value": 39.5,
                "period": "FY 2025-26",
                "chart_type": "bar",
                "data_shape": "category_compare",
                "higher_is_better": True,
                "breakdown_label": "Metric",
                "benchmark_label": "UPA-era Benchmark",
                "series": category_series(
                    {
                        "Avg Freight Speed (km/h)": {"current": 32, "benchmark": 24},
                        "Avg Express Speed (km/h)": {"current": 62, "benchmark": 51},
                        "Line Capacity Use (%)": {"current": 115, "benchmark": 140},
                        "Electrified Route (%)": {"current": 97, "benchmark": 42},
                    },
                    current_keys=("current",),
                ),
            },
        ],
    },
    {
        "code": "POW",
        "name": "Ministry of Power",
        "description": "Responsible for electricity generation, transmission, distribution reform, and tariff policy.",
        "kpis": [
            {
                "name": "Industrial Tariffs",
                "category": "pricing",
                "unit": "₹/kWh",
                "target_value": 7.0,
                "period": "FY 2025-26",
                "chart_type": "line",
                "data_shape": "time_breakdown",
                "hero": True,
                "higher_is_better": False,
                "breakdown_label": "State",
                "series": time_breakdown_series(
                    {
                        "Maharashtra": tariff_mh,
                        "Gujarat": tariff_gj,
                        "Tamil Nadu": tariff_tn,
                        "Uttar Pradesh": tariff_up,
                    }
                ),
            },
            {
                "name": "Discom Financial Health",
                "category": "distribution reform",
                "unit": "₹'000 Cr losses",
                "target_value": 40.0,
                "period": "FY 2025-26",
                "chart_type": "dual_axis",
                "data_shape": "time_dual",
                "higher_is_better": False,
                "secondary_label": "AT&C Losses",
                "secondary_unit": "%",
                "series": time_dual_series(discom_losses, atc_losses),
            },
            {
                "name": "Power Availability",
                "category": "reliability",
                "unit": "% availability",
                "target_value": 100.0,
                "period": "FY 2025-26",
                "chart_type": "line",
                "data_shape": "time_line",
                "higher_is_better": True,
                "series": time_line_series(power_availability, 100.0),
            },
        ],
    },
    {
        "code": "DEF",
        "name": "Ministry of Defence",
        "description": "Responsible for national security, armed forces modernisation, and defence production.",
        "kpis": [
            {
                "name": "Defence CapEx",
                "category": "budget",
                "unit": "% of GDP",
                "target_value": 1.6,
                "period": "FY 2025-26",
                "chart_type": "line",
                "data_shape": "time_line",
                "hero": True,
                "higher_is_better": True,
                "benchmark_label": "UPA-era Average",
                "series": time_line_series(defence_capex, defence_capex_benchmark),
            },
            {
                "name": "Domestic MIC Development",
                "category": "defence production",
                "unit": "% indigenised",
                "target_value": 75.0,
                "period": "FY 2025-26",
                "chart_type": "stacked_bar",
                "data_shape": "category_compare",
                "higher_is_better": True,
                "breakdown_label": "Platform Type",
                "series": category_series(
                    {
                        "Aircraft": {"Design": 15, "Development": 20, "Production": 35, "Induction": 22},
                        "Ships": {"Design": 18, "Development": 22, "Production": 38, "Induction": 14},
                        "Missiles": {"Design": 20, "Development": 25, "Production": 30, "Induction": 18},
                        "Armoured Vehicles": {"Design": 12, "Development": 18, "Production": 42, "Induction": 20},
                    }
                ),
            },
            {
                "name": "Force Modernisation",
                "category": "equipment readiness",
                "unit": "% of fleet",
                "target_value": 85.0,
                "period": "FY 2025-26",
                "chart_type": "grouped_bar",
                "data_shape": "category_compare",
                "higher_is_better": True,
                "breakdown_label": "Equipment Category",
                "series": category_series(
                    {
                        "Fighter Squadrons": {"operational": 68, "upgrading": 22, "obsolete": 10},
                        "Artillery": {"operational": 74, "upgrading": 18, "obsolete": 8},
                        "Naval Vessels": {"operational": 81, "upgrading": 14, "obsolete": 5},
                        "Air Defence": {"operational": 71, "upgrading": 21, "obsolete": 8},
                    },
                    current_keys=("operational",),
                ),
            },
        ],
    },
    {
        "code": "EDU",
        "name": "Ministry of Education",
        "description": "Responsible for school and higher education policy, learning outcomes, and enrollment.",
        "kpis": [
            {
                "name": "Learning Outcomes",
                "category": "learning outcomes",
                "unit": "% proficient",
                "target_value": 65.0,
                "period": "FY 2025-26",
                "chart_type": "grouped_bar",
                "data_shape": "category_compare",
                "hero": True,
                "higher_is_better": True,
                "breakdown_label": "Grade / Subject",
                "series": category_series(
                    {
                        "Grade 3 Reading": {"ASER": 42, "NAS": 48},
                        "Grade 5 Math": {"ASER": 31, "NAS": 39},
                        "Grade 8 Language": {"ASER": 58, "NAS": 61},
                        "Grade 8 Math": {"ASER": 34, "NAS": 37},
                    }
                ),
            },
            {
                "name": "Exam Integrity",
                "category": "school performance",
                "unit": "%",
                "target_value": 95.0,
                "period": "FY 2025-26",
                "chart_type": "bar",
                "data_shape": "category_compare",
                "higher_is_better": True,
                "breakdown_label": "Metric",
                "series": category_series(
                    {
                        "Enrollment Rate": {"govt": 94, "private": 97},
                        "Pass Rate": {"govt": 83, "private": 91},
                        "Retention Rate": {"govt": 78, "private": 89},
                    }
                ),
            },
            {
                "name": "Enrollment Quality",
                "category": "school quality",
                "unit": "quality index",
                "target_value": 75.0,
                "period": "FY 2025-26",
                "chart_type": "line",
                "data_shape": "time_line",
                "higher_is_better": True,
                "series": time_line_series(lerp(52.0, 68.0, jitter=1.0, seed=34), 75.0),
            },
        ],
    },
    {
        "code": "SKILL",
        "name": "Ministry of Skill Development & Entrepreneurship",
        "description": "Responsible for vocational training, apprenticeships, and youth employability.",
        "kpis": [
            {
                "name": "Youth NEET Rate",
                "category": "employability",
                "unit": "%",
                "target_value": 20.0,
                "period": "FY 2025-26",
                "chart_type": "line",
                "data_shape": "time_line",
                "hero": True,
                "higher_is_better": False,
                "benchmark_label": "2014 Baseline",
                "series": time_line_series(neet_rate, neet_baseline),
            },
            {
                "name": "Apprenticeship Utilisation",
                "category": "training",
                "unit": "₹ Cr",
                "target_value": 7800.0,
                "period": "FY 2025-26",
                "chart_type": "grouped_bar",
                "data_shape": "time_dual",
                "higher_is_better": True,
                "secondary_label": "Actual Spend",
                "secondary_unit": "₹ Cr",
                "benchmark_label": "Budget Allocation",
                "series": time_dual_series(apprentice_budget, apprentice_actual),
            },
            {
                "name": "Job Creation",
                "category": "employment",
                "unit": "Lakh formal jobs/yr",
                "target_value": 90.0,
                "period": "FY 2025-26",
                "chart_type": "line",
                "data_shape": "time_line",
                "higher_is_better": True,
                "series": time_line_series(jobs_created, 90.0),
            },
        ],
    },
    {
        "code": "AGRI",
        "name": "Ministry of Agriculture & Farmers Welfare",
        "description": "Responsible for agricultural policy, farmer income support, crop production, and rural credit.",
        "kpis": [
            {
                "name": "Real Farmer Income",
                "category": "farmer welfare",
                "unit": "index (2014=100)",
                "target_value": 200.0,
                "period": "FY 2025-26",
                "chart_type": "line",
                "data_shape": "time_line",
                "hero": True,
                "higher_is_better": True,
                "series": time_line_series(farmer_income, 200.0),
            },
            {
                "name": "Ethanol Programme",
                "category": "renewable fuel",
                "unit": "Cr litres blended",
                "target_value": 1016.0,
                "period": "FY 2025-26",
                "chart_type": "dual_axis",
                "data_shape": "time_dual",
                "higher_is_better": True,
                "secondary_label": "Forex Savings",
                "secondary_unit": "₹'000 Cr",
                "series": time_dual_series(ethanol_volume, ethanol_forex),
            },
            {
                "name": "Food Inflation",
                "category": "price stability",
                "unit": "% CPI Food YoY",
                "target_value": 4.0,
                "period": "FY 2025-26",
                "chart_type": "line",
                "data_shape": "time_line",
                "higher_is_better": False,
                "series": time_line_series(food_inflation, 4.0),
            },
        ],
    },
    {
        "code": "PETRO",
        "name": "Ministry of Petroleum & Natural Gas",
        "description": "Responsible for oil & gas exploration, refining, distribution, and energy security.",
        "kpis": [
            {
                "name": "Oil Import Dependence",
                "category": "energy security",
                "unit": "% of consumption",
                "target_value": 67.0,
                "period": "FY 2025-26",
                "chart_type": "line",
                "data_shape": "time_line",
                "hero": True,
                "higher_is_better": False,
                "series": time_line_series(oil_dependence, 67.0),
            },
            {
                "name": "Ethanol Blending %",
                "category": "renewable fuel",
                "unit": "% blend",
                "target_value": 20.0,
                "period": "FY 2025-26",
                "chart_type": "line",
                "data_shape": "time_line",
                "higher_is_better": True,
                "series": time_line_series(ethanol_blend, 20.0),
            },
            {
                "name": "Refining Efficiency",
                "category": "refining",
                "unit": "MMT throughput",
                "target_value": 280.0,
                "period": "FY 2025-26",
                "chart_type": "dual_axis",
                "data_shape": "time_dual",
                "higher_is_better": True,
                "secondary_label": "Refining Cost",
                "secondary_unit": "$/bbl",
                "series": time_dual_series(refining_throughput, refining_cost),
            },
        ],
    },
    {
        "code": "ROAD",
        "name": "Ministry of Road Transport & Highways",
        "description": "Responsible for national highways, logistics efficiency, and road safety.",
        "kpis": [
            {
                "name": "Logistics Cost %",
                "category": "logistics",
                "unit": "% of GDP",
                "target_value": 8.0,
                "period": "FY 2025-26",
                "chart_type": "line",
                "data_shape": "time_line",
                "hero": True,
                "higher_is_better": False,
                "series": time_line_series(logistics_cost, 8.0),
            },
            {
                "name": "Highway Construction",
                "category": "infrastructure",
                "unit": "km/day",
                "target_value": 20.0,
                "period": "FY 2025-26",
                "chart_type": "bar",
                "data_shape": "time_line",
                "higher_is_better": True,
                "benchmark_label": "Pace Benchmark",
                "series": time_line_series(highway_pace, 20.0),
            },
            {
                "name": "Modal Share",
                "category": "logistics mix",
                "unit": "% of freight",
                "target_value": 55.0,
                "period": "FY 2025-26",
                "chart_type": "stacked_area",
                "data_shape": "time_breakdown",
                "higher_is_better": False,
                "breakdown_label": "Mode",
                "series": time_breakdown_series({"Road": modal_road, "Rail": modal_rail, "Multimodal": modal_multi}),
            },
        ],
    },
]


EVENTS: list[dict] = [
    {"label": "GST Implementation", "year": 2017, "category": "policy", "ministry_codes": ["FIN"]},
    {"label": "National Education Policy 2020", "year": 2020, "category": "policy", "ministry_codes": ["EDU"]},
    {"label": "PLI Scheme Launch", "year": 2020, "category": "policy", "ministry_codes": ["COMM", "DEF"]},
    {"label": "COVID-19 Pandemic", "year": 2020, "category": "covid", "ministry_codes": None},
    {"label": "PM Gati Shakti Launch", "year": 2021, "category": "policy", "ministry_codes": ["RAIL", "ROAD"]},
    {"label": "Ethanol Blending Push (EBP)", "year": 2018, "category": "policy", "ministry_codes": ["PETRO", "AGRI"]},
    {"label": "Global Energy Price Shock", "year": 2022, "category": "global", "ministry_codes": None},
]


def run() -> None:
    Base.metadata.create_all(bind=engine)
    sync_schema()
    from app.connectors.tier_a.spec import TIER_A_BY_NAME
    from app.connectors.tier_b.spec import TIER_B_BY_NAME

    # Presentation + series for all 30 KPIs across the 10 ministries are owned by
    # the tier pipelines (real curated data). seed_dashboard only creates the
    # rows and non-tier synthetic series (of which there are now none).
    TIER_BY_NAME = {**TIER_A_BY_NAME, **TIER_B_BY_NAME}

    db = SessionLocal()
    try:
        keep_codes = {m["code"] for m in MINISTRIES}
        for ministry in db.query(Ministry).all():
            if ministry.code not in keep_codes:
                db.delete(ministry)
        db.commit()

        for m_def in MINISTRIES:
            ministry = db.query(Ministry).filter(Ministry.code == m_def["code"]).first()
            if ministry is None:
                ministry = Ministry(name=m_def["name"], code=m_def["code"], description=m_def["description"])
                db.add(ministry)
                db.flush()
            else:
                ministry.name = m_def["name"]
                ministry.description = m_def["description"]

            keep_names = {k["name"] for k in m_def["kpis"]}
            for kpi in list(ministry.kpis):
                if kpi.name not in keep_names:
                    db.delete(kpi)
            db.flush()

            for k_def in m_def["kpis"]:
                kpi = (
                    db.query(KPI)
                    .filter(KPI.ministry_id == ministry.id, KPI.name == k_def["name"])
                    .first()
                )
                if kpi is None:
                    kpi = KPI(ministry_id=ministry.id, name=k_def["name"], current_value=0.0)
                    db.add(kpi)

                is_tier_a = (m_def["code"], k_def["name"]) in TIER_BY_NAME

                kpi.category = k_def["category"]
                kpi.period = k_def["period"]
                kpi.hero = k_def.get("hero", False)

                if is_tier_a:
                    # Presentation + series for this KPI are owned by the tier
                    # pipeline (`python -m app.tier_a_pipeline` / `tier_b_pipeline`,
                    # real data). Only create the row + keep hero/category/period
                    # here; never write a synthetic series or clobber a real value.
                    spec = TIER_BY_NAME[(m_def["code"], k_def["name"])]
                    if kpi.id is None or kpi.current_value in (None, 0.0):
                        kpi.current_value = 0.0
                    kpi.unit = spec.unit
                    kpi.chart_type = spec.chart_type
                    kpi.data_shape = spec.data_shape
                    kpi.higher_is_better = spec.higher_is_better
                    kpi.target_value = spec.target.official if spec.target.official is not None else 0.0
                    kpi.aspirational_target = spec.target.aspirational
                    kpi.secondary_label = spec.secondary_label
                    kpi.secondary_unit = spec.secondary_unit
                    kpi.benchmark_label = spec.target.official_label
                    kpi.aspirational_label = spec.target.aspirational_label
                    kpi.breakdown_label = spec.breakdown_label
                    kpi.display_title = spec.display_title
                    kpi.plain_note = spec.plain_note
                    kpi.updated_at = datetime.now(timezone.utc)
                    db.flush()
                    continue

                kpi.unit = k_def["unit"]
                kpi.target_value = k_def["target_value"]
                kpi.chart_type = k_def["chart_type"]
                kpi.data_shape = k_def["data_shape"]
                kpi.higher_is_better = k_def.get("higher_is_better", True)
                kpi.secondary_label = k_def.get("secondary_label")
                kpi.secondary_unit = k_def.get("secondary_unit")
                kpi.benchmark_label = k_def.get("benchmark_label", "Official Target")
                kpi.breakdown_label = k_def.get("breakdown_label")
                kpi.current_value = k_def["series"][-1]["value"]
                kpi.updated_at = datetime.now(timezone.utc)
                db.flush()

                db.query(KPISeriesPoint).filter(KPISeriesPoint.kpi_id == kpi.id).delete()
                for row in k_def["series"]:
                    db.add(KPISeriesPoint(kpi_id=kpi.id, **row))

            db.commit()

        db.query(Event).delete()
        for e in EVENTS:
            db.add(Event(**e))
        db.commit()

        print(f"Seeded {len(MINISTRIES)} ministries with curated KPI series and {len(EVENTS)} events.")
    finally:
        db.close()


if __name__ == "__main__":
    run()
