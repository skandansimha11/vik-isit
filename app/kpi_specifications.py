"""Single source of truth for the dashboard's 30 KPI definitions.

Each entry documents what the KPI measures, where it would come from in the
real world, how reliable that data is, and what caveats must accompany any
AI-generated commentary about it. This module is metadata only - it does not
fetch or store values (see app/connectors/ for that) - but every value shown
in the dashboard should be traceable back to one of these specs.

KPI `name` fields are matched exactly to the KPI names seeded by
app/seed_dashboard.py (the dataset that actually powers the running
dashboard) so that app.claude_service and app.tarka_chatbot can look up a
spec for any KPI a user is looking at.

IMPORTANT: this app ships with illustrative/demo data, not live-scraped
official statistics. The `source_url` / `source_name` fields below describe
where a production build WOULD pull from; they are reference pointers for a
future connector, not a claim that this app currently scrapes them. Treat
data_quality and proxy_based as authoritative constraints on how Tarka and
the insights engine are allowed to talk about a KPI, regardless of where the
number in the DB actually came from.
"""

from __future__ import annotations

from dataclasses import dataclass

DATA_QUALITY_LEVELS = ("HIGH", "MEDIUM", "LOW")
TIERS = ("A", "B", "C")  # A = build first, B = secondary, C = defer/explicit proxy


@dataclass(frozen=True)
class KPISpec:
    ministry_code: str
    key: str  # stable slug
    name: str  # must match KPI.name in app/seed_dashboard.py exactly
    definition: str
    data_quality: str  # HIGH | MEDIUM | LOW
    source_name: str
    source_url: str
    update_frequency: str
    time_period: str
    units: str
    caveats: tuple[str, ...]
    calculation: str
    data_points: tuple[str, ...]
    proxy_based: bool
    chart_type: str
    tier: str
    formula: str | None = None

    def __post_init__(self):
        if self.data_quality not in DATA_QUALITY_LEVELS:
            raise ValueError(f"{self.key}: bad data_quality {self.data_quality!r}")
        if self.tier not in TIERS:
            raise ValueError(f"{self.key}: bad tier {self.tier!r}")


# ---------------------------------------------------------------------------
# MINISTRY 1: FINANCE (FIN)
# ---------------------------------------------------------------------------

_FINANCE = [
    KPISpec(
        ministry_code="FIN",
        key="fiscal_deficit_pct_gdp",
        name="Fiscal Deficit",
        definition=(
            "(Total Expenditure - Revenue Receipts - Non-debt Capital Receipts) "
            "/ Nominal GDP x 100"
        ),
        data_quality="HIGH",
        source_name="Economic Survey Statistical Appendix (Receipts & Expenditure table)",
        source_url="https://www.indiabudget.gov.in/economicsurvey/",
        update_frequency="Annual (FY basis)",
        time_period="FY 2014-15 onwards",
        units="% of GDP",
        caveats=(
            "GDP series revisions affect this ratio retroactively.",
            "Use a consistent GDP base year (currently 2011-12 or the latest revision).",
            "Show Actual / Revised Estimate / Budget Estimate separately where available "
            "- they are not interchangeable.",
        ),
        calculation="Straightforward division; no derived/composite steps.",
        data_points=("Total Expenditure (Rs)", "Revenue Receipts (Rs)", "Non-debt Capital Receipts (Rs)", "Nominal GDP (Rs)"),
        proxy_based=False,
        chart_type="line",
        tier="A",
        formula="(total_expenditure - revenue_receipts - non_debt_capital_receipts) / nominal_gdp * 100",
    ),
    KPISpec(
        ministry_code="FIN",
        key="tax_administration_intensity",
        name="Tax Harassment Cases",
        definition=(
            "Composite proxy using scrutiny notices issued, reassessments reopened beyond 6 "
            "years, faceless appeals pending, and taxpayer grievances filed."
        ),
        data_quality="LOW",
        source_name="CBDT Annual Reports + Parliamentary replies + CAG Audit Reports",
        source_url="https://incometaxindia.gov.in/Pages/Direct-Taxes-Data.aspx",
        update_frequency="Annual (occasional quarterly via parliamentary updates)",
        time_period="FY 2014-15 onwards",
        units="'000 cases",
        caveats=(
            "No official 'harassment index' exists - this is an assembled proxy, not a "
            "published series.",
            "Requires manual aggregation across CBDT, CAG and parliamentary sources.",
            "Parliamentary answer data is incomplete and inconsistent across sessions.",
            "PROXY STATUS: any AI commentary must explicitly call this the 'best available "
            "proxy' and never present it as a definitive, official metric.",
        ),
        calculation="Count-based aggregation across four sub-categories; no formula beyond simple sums.",
        data_points=("scrutiny_notices", "reassessments_over_6yr", "faceless_appeals_pending", "taxpayer_grievances"),
        proxy_based=True,
        chart_type="grouped_bar",
        tier="C",
    ),
    KPISpec(
        ministry_code="FIN",
        key="tax_collection_growth",
        name="Tax Collection Growth",
        definition=(
            "Growth = (Current Year Tax Collections - Previous Year) / Previous Year x 100, "
            "shown alongside Nominal GDP Growth to separate real buoyancy from inflation."
        ),
        data_quality="HIGH",
        source_name="CBDT Direct Taxes Data + Economic Survey / Union Budget",
        source_url="https://incometaxindia.gov.in/Pages/Direct-Taxes-Data.aspx",
        update_frequency="Monthly (provisional) / Annual (final)",
        time_period="FY 2014-15 onwards (monthly from FY 2020-21 where available)",
        units="% YoY",
        caveats=(
            "Distinguish Gross Tax Revenue from Net Tax Revenue to Centre - they diverge "
            "materially due to devolution.",
            "High nominal growth can be a pure inflation effect; compare against the paired "
            "Nominal GDP Growth series before crediting policy.",
            "One-off disinvestment receipts can spike a single year's number.",
            "Show direct and indirect tax series separately, not just the blended total, where possible.",
        ),
        calculation="Standard YoY growth formula; tax buoyancy = tax growth / GDP growth.",
        data_points=("gross_tax_revenue_curr", "gross_tax_revenue_prev", "nominal_gdp_growth_pct"),
        proxy_based=False,
        chart_type="dual_axis",
        tier="A",
        formula="((gtr_curr - gtr_prev) / gtr_prev) * 100 ; buoyancy = tax_growth_pct / gdp_growth_pct",
    ),
]

# ---------------------------------------------------------------------------
# MINISTRY 2: PETROLEUM & NATURAL GAS (PETRO) - Tier A, excellent data quality
# ---------------------------------------------------------------------------

_PETROLEUM = [
    KPISpec(
        ministry_code="PETRO",
        key="oil_import_dependence",
        name="Oil Import Dependence",
        definition="Net crude oil imports as a % of total domestic crude consumption.",
        data_quality="HIGH",
        source_name="PPAC (Petroleum Planning & Analysis Cell) monthly snapshot",
        source_url="https://ppac.gov.in/",
        update_frequency="Monthly",
        time_period="FY 2014-15 onwards",
        units="% of consumption",
        caveats=(
            "Import dependence is driven mostly by global crude prices and domestic demand "
            "growth, not policy alone - don't read short-term moves as a domestic production story.",
            "Strategic reserve drawdowns can temporarily distort the ratio in a single month.",
        ),
        calculation="net_crude_imports / total_crude_consumption * 100",
        data_points=("net_crude_imports_mt", "total_crude_consumption_mt"),
        proxy_based=False,
        chart_type="line",
        tier="A",
        formula="net_crude_imports_mt / total_crude_consumption_mt * 100",
    ),
    KPISpec(
        ministry_code="PETRO",
        key="ethanol_blending",
        name="Ethanol Blending %",
        definition="Average ethanol blending percentage achieved in petrol nationally (Ethanol Blending Programme).",
        data_quality="HIGH",
        source_name="PPAC Ethanol Blending Programme monthly bulletin",
        source_url="https://ppac.gov.in/ethanol-blending",
        update_frequency="Monthly",
        time_period="FY 2014-15 onwards (programme accelerated from FY2018-19)",
        units="% blend",
        caveats=(
            "Blending % is a national average - state-level achievement varies widely and can "
            "mask supply bottlenecks in specific regions.",
            "Feedstock diversion (foodgrain vs. molasses vs. damaged grain) has its own food-security "
            "debate that this metric does not capture.",
        ),
        calculation="ethanol_supplied_litres / (petrol_consumption_litres + ethanol_supplied_litres) * 100",
        data_points=("ethanol_supplied_million_litres", "petrol_consumption_million_litres"),
        proxy_based=False,
        chart_type="line",
        tier="A",
        formula="ethanol_litres / (petrol_litres + ethanol_litres) * 100",
    ),
    KPISpec(
        ministry_code="PETRO",
        key="refining_efficiency",
        name="Refining Efficiency",
        definition="Refinery throughput (MMT processed) shown alongside average refining cost ($/bbl).",
        data_quality="MEDIUM",
        source_name="PPAC refinery performance bulletin",
        source_url="https://ppac.gov.in/",
        update_frequency="Monthly",
        time_period="FY 2014-15 onwards",
        units="MMT throughput",
        caveats=(
            "Throughput growth can reflect new refining capacity coming online rather than "
            "existing-asset efficiency gains - check capacity-utilisation %, not just raw MMT.",
            "Refining cost ($/bbl) is sensitive to global crude price swings unrelated to domestic "
            "operational efficiency.",
        ),
        calculation="Direct sum of reported monthly refinery throughput; cost is a weighted average.",
        data_points=("refinery_throughput_mmt", "refining_cost_usd_per_bbl", "refining_capacity_mmt"),
        proxy_based=False,
        chart_type="dual_axis",
        tier="A",
    ),
]

# ---------------------------------------------------------------------------
# MINISTRY 3: AGRICULTURE & FARMERS WELFARE (AGRI) - Tier A, mixed quality
# ---------------------------------------------------------------------------

_AGRICULTURE = [
    KPISpec(
        ministry_code="AGRI",
        key="real_farmer_income",
        name="Real Farmer Income",
        definition="Real (CPI-deflated) farmer household income index, base year 2014=100.",
        data_quality="MEDIUM",
        source_name="National Accounts Statistics (MoSPI), CPI deflator (MoSPI/RBI)",
        source_url="https://www.mospi.gov.in/",
        update_frequency="Annual",
        time_period="FY 2014-15 onwards",
        units="index (2014=100)",
        caveats=(
            "Official household-level farmer income surveys (Situation Assessment Survey) are "
            "infrequent (roughly once a decade) - annual figures are model-based estimates, not "
            "direct measurement.",
            "Aggregate agricultural GVA growth is not the same as median farmer household income growth; "
            "large-holding bias can inflate the aggregate picture.",
        ),
        calculation="Deflate nominal agri income series by CPI-Rural, then index to the 2014 base year.",
        data_points=("nominal_agri_income", "cpi_rural_index"),
        proxy_based=True,
        chart_type="line",
        tier="A",
        formula="real_income = nominal_income / (cpi_rural_index / 100); index to 2014=100",
    ),
    KPISpec(
        ministry_code="AGRI",
        key="ethanol_programme_agri",
        name="Ethanol Programme",
        definition="Ethanol volume blended (crore litres) and associated forex savings, from feedstock supplied under the Ethanol Blending Programme.",
        data_quality="HIGH",
        source_name="PPAC Ethanol Blending Programme bulletin (shared source with Petroleum ministry)",
        source_url="https://ppac.gov.in/ethanol-blending",
        update_frequency="Monthly",
        time_period="FY 2018-19 onwards (programme acceleration)",
        units="Cr litres blended",
        caveats=(
            "Overlaps with the Petroleum ministry's Ethanol Blending % KPI - treat as the same "
            "underlying data source viewed from the agricultural-supply side, not an independent confirmation.",
            "Forex savings figures are estimated from an assumed crude-oil substitution price, "
            "which itself fluctuates.",
        ),
        calculation="Sum of feedstock volumes by category; forex savings = litres_saved * assumed crude-equivalent price.",
        data_points=("grain_based_ethanol_litres", "molasses_based_ethanol_litres", "forex_savings_rs_cr"),
        proxy_based=False,
        chart_type="dual_axis",
        tier="A",
    ),
    KPISpec(
        ministry_code="AGRI",
        key="food_inflation",
        name="Food Inflation",
        definition="Year-on-year % change in the CPI food & beverages sub-index.",
        data_quality="HIGH",
        source_name="Consumer Price Index (MoSPI), cross-checked against RBI inflation reports",
        source_url="https://mospi.gov.in/cpi",
        update_frequency="Monthly",
        time_period="FY 2014-15 onwards",
        units="% CPI Food YoY",
        caveats=(
            "Food inflation is heavily weather- and monsoon-driven in the short run - a single bad "
            "month should not be read as a policy failure or success signal.",
            "CPI weight revisions (base-year updates) break strict comparability across the full window.",
        ),
        calculation="pct_change(cpi_food_index) over 12 months (YoY)",
        data_points=("cpi_food_index_current", "cpi_food_index_prior_year"),
        proxy_based=False,
        chart_type="line",
        tier="A",
    ),
]

# ---------------------------------------------------------------------------
# MINISTRY 4: RAILWAYS (RAIL)
# ---------------------------------------------------------------------------

_RAILWAYS = [
    KPISpec(
        ministry_code="RAIL",
        key="freight_volume_growth",
        name="Freight Volume Growth",
        definition="YoY growth in freight loaded (Million Tonnes), against the annual target.",
        data_quality="HIGH",
        source_name="Indian Railways Statistical Statements / Year Book",
        source_url="https://indianrailways.gov.in/railwayboard/",
        update_frequency="Monthly (provisional) / Annual (final)",
        time_period="FY 2014-15 onwards",
        units="% YoY",
        caveats=(
            "Freight mix shifts (e.g. more coal vs. more containerised cargo) change average haul "
            "length, so tonnage growth and NTKM growth can diverge - check both where available.",
            "COVID-year (FY2020-21) comparisons need a base-effect caveat.",
        ),
        calculation="pct_change(freight_loaded_mt) YoY",
        data_points=("freight_loaded_mt_curr", "freight_loaded_mt_prev"),
        proxy_based=False,
        chart_type="line",
        tier="A",
    ),
    KPISpec(
        ministry_code="RAIL",
        key="rail_market_share",
        name="Rail Market Share",
        definition="Rail's % share of total inland freight tonnage, shown against road's share.",
        data_quality="MEDIUM",
        source_name="Indian Railways Statistical Statements + MoRTH logistics data (for the road-share comparison)",
        source_url="https://indianrailways.gov.in/railwayboard/",
        update_frequency="Annual",
        time_period="FY 2014-15 onwards",
        units="% of freight",
        caveats=(
            "Rail and road freight are measured by different agencies with different methodologies "
            "- the two shares in this chart are not from a single reconciled national freight survey.",
            "Rail's freight modal share has structurally declined since the 1990s; a single year's "
            "uptick should not be read as a reversal without a multi-year trend.",
        ),
        calculation="rail_freight_tonnage / total_inland_freight_tonnage * 100",
        data_points=("rail_freight_tonnage", "road_freight_tonnage", "total_inland_freight_tonnage"),
        proxy_based=False,
        chart_type="stacked_area",
        tier="B",
    ),
    KPISpec(
        ministry_code="RAIL",
        key="train_speeds_capacity",
        name="Train Speeds & Capacity",
        definition=(
            "Composite service-quality index: average freight speed (km/h), average express speed "
            "(km/h), line capacity utilisation (%), and electrified route (%), benchmarked against "
            "UPA-era figures."
        ),
        data_quality="MEDIUM",
        source_name="Indian Railways operational performance reports",
        source_url="https://indianrailways.gov.in/railwayboard/",
        update_frequency="Annual",
        time_period="FY 2014-15 onwards, benchmarked against a pre-2014 baseline",
        units="index",
        caveats=(
            "This is a composite of four different metrics on different scales - treat the 'index' "
            "as illustrative, not a single official published statistic.",
            "Line capacity utilisation above 100% indicates congestion, not necessarily good "
            "performance; don't treat 'higher is always better' uncritically for that sub-metric.",
        ),
        calculation="Reported directly per sub-metric; no single official composite formula exists.",
        data_points=("avg_freight_speed_kmh", "avg_express_speed_kmh", "line_capacity_utilisation_pct", "electrified_route_pct"),
        proxy_based=True,
        chart_type="bar",
        tier="B",
    ),
]

# ---------------------------------------------------------------------------
# MINISTRY 5: POWER (POW)
# ---------------------------------------------------------------------------

_POWER = [
    KPISpec(
        ministry_code="POW",
        key="industrial_tariffs",
        name="Industrial Tariffs",
        definition="Average industrial electricity tariff (Rs/kWh), by state.",
        data_quality="MEDIUM",
        source_name="State Electricity Regulatory Commission tariff orders",
        source_url="https://cea.nic.in/",
        update_frequency="Annual (tariff order cycle)",
        time_period="FY 2014-15 onwards",
        units="Rs/kWh",
        caveats=(
            "State tariff orders bundle different cross-subsidy structures - a raw Rs/kWh figure "
            "isn't fully comparable across states without normalising for slab structure.",
        ),
        calculation="Weighted average tariff per state, as published in the tariff order.",
        data_points=("state_industrial_tariff_rs_per_kwh",),
        proxy_based=False,
        chart_type="line",
        tier="B",
    ),
    KPISpec(
        ministry_code="POW",
        key="discom_financial_health",
        name="Discom Financial Health",
        definition="Distribution utility (discom) accumulated losses (Rs '000 Cr), shown alongside AT&C (Aggregate Technical & Commercial) losses %.",
        data_quality="HIGH",
        source_name="PFC 'Report on Performance of Power Utilities' (national + state-wise)",
        source_url="https://pfcindia.com/",
        update_frequency="Annual",
        time_period="FY 2014-15 onwards",
        units="Rs '000 Cr losses",
        caveats=(
            "There are methodological breaks in the AT&C definition across report editions - "
            "don't treat the full series as strictly comparable without noting the break years.",
            "National average masks very large state-level dispersion; always show a state range, "
            "not just the headline number.",
        ),
        calculation="(energy_input - energy_billed_realised) / energy_input * 100 for AT&C%; discom losses summed from utility balance sheets.",
        data_points=("energy_input_units", "energy_billed_realised_units", "discom_accumulated_losses_rs_cr"),
        proxy_based=False,
        chart_type="dual_axis",
        tier="A",
        formula="atc_pct = (energy_input_units - energy_billed_realised_units) / energy_input_units * 100",
    ),
    KPISpec(
        ministry_code="POW",
        key="power_availability",
        name="Power Availability",
        definition="% of time electricity supply met demand (no scheduled/unscheduled outage), nationally.",
        data_quality="MEDIUM",
        source_name="CEA Power Supply Position reports",
        source_url="https://cea.nic.in/",
        update_frequency="Monthly",
        time_period="FY 2014-15 onwards",
        units="% availability",
        caveats=(
            "National averages hide rural/urban and state-level gaps in actual reliability - a high "
            "national figure can coexist with persistent rural load-shedding.",
        ),
        calculation="hours_supplied / hours_demanded * 100, aggregated nationally.",
        data_points=("hours_supplied", "hours_demanded"),
        proxy_based=False,
        chart_type="line",
        tier="B",
    ),
]

# ---------------------------------------------------------------------------
# MINISTRY 6: COMMERCE & INDUSTRY (COMM)
# ---------------------------------------------------------------------------

_COMMERCE = [
    KPISpec(
        ministry_code="COMM",
        key="industrial_import_dependence",
        name="Industrial Imports %",
        definition="Net imports of manufactured / capital / intermediate goods (excluding oil and gold) as a % of domestic consumption of those goods. An assembled estimate - there is no single official series.",
        data_quality="LOW",
        source_name="DGCI&S trade data cross-referenced with MoSPI National Accounts / IIP domestic production; RBI & NITI Aayog import-intensity studies",
        source_url="https://www.commerce.gov.in/",
        update_frequency="Annual (requires manual cross-referencing)",
        time_period="FY 2014-15 onwards",
        units="% of demand",
        caveats=(
            "Requires matching HS trade codes to IIP production categories, which is not a 1:1 "
            "mapping - treat any single-number result as an estimate range, not a precise figure.",
            "'Industrial goods' spans a very heterogeneous basket (electronics, capital machinery, "
            "chemicals); a single blended % can mask sharply different import-dependence by sub-sector.",
        ),
        calculation="category_imports / (category_imports + domestic_production - category_exports)",
        data_points=("category_imports", "domestic_production", "category_exports"),
        proxy_based=True,
        chart_type="line",
        tier="C",
    ),
    KPISpec(
        ministry_code="COMM",
        key="manufacturing_growth",
        name="Manufacturing Growth",
        definition="Manufacturing value added as a share of total Gross Value Added (current prices). The headline chart tracks this share; year-on-year IIP-manufacturing growth is carried as the secondary series.",
        data_quality="MEDIUM",
        source_name="MoSPI National Accounts Statistics (manufacturing GVA) + Index of Industrial Production",
        source_url="https://www.mospi.gov.in/",
        update_frequency="Annual (GVA share) / Monthly (IIP)",
        time_period="FY 2014-15 onwards",
        units="% of GVA",
        caveats=(
            "The GVA share has been broadly flat near 17% for a decade despite 'Make in India' - "
            "check whether any single-year move is a real structural shift or a base-price artefact.",
            "IIP is a volume index with a base-year weighting that periodically changes, which can "
            "break strict comparability of the secondary growth series across the full window.",
        ),
        calculation="manufacturing_gva / total_gva * 100 (current prices)",
        data_points=("manufacturing_gva_rs_cr", "total_gva_rs_cr", "iip_manufacturing_growth_pct"),
        proxy_based=False,
        chart_type="line",
        tier="B",
    ),
    KPISpec(
        ministry_code="COMM",
        key="pli_effectiveness",
        name="PLI Effectiveness",
        definition="Cumulative investment actually made under the Production-Linked Incentive schemes as a % of the investment companies committed.",
        data_quality="MEDIUM",
        source_name="DPIIT / sectoral ministry PLI progress reviews; PIB releases; Parliament replies",
        source_url="https://dpiit.gov.in/",
        update_frequency="Annual / Quarterly",
        time_period="FY 2020-21 onwards (scheme launch)",
        units="% of committed investment",
        caveats=(
            "Realisation figures are largely self-reported by participating companies, not "
            "independently audited investment/output figures.",
            "Investment realised is not the real test - genuine domestic value-addition (vs "
            "imported-kit assembly) and net forex impact matter more, and are weaker in "
            "assembly-heavy sectors like electronics.",
        ),
        calculation="cumulative_investment_realised / cumulative_investment_committed * 100",
        data_points=("investment_realised_rs_cr", "investment_committed_rs_cr"),
        proxy_based=True,
        chart_type="line",
        tier="B",
    ),
]

# ---------------------------------------------------------------------------
# MINISTRY 7: DEFENCE (DEF)
# ---------------------------------------------------------------------------

_DEFENCE = [
    KPISpec(
        ministry_code="DEF",
        key="defence_capex",
        name="Defence CapEx",
        definition="Capital outlay on the Defence Services (spend on new equipment and platforms) as a % of nominal GDP.",
        data_quality="HIGH",
        source_name="Union Budget - Defence Services Estimates (Capital Outlay); MoSPI Nominal GDP; PRS Legislative Research",
        source_url="https://www.indiabudget.gov.in/",
        update_frequency="Annual",
        time_period="FY 2014-15 onwards",
        units="% of GDP",
        caveats=(
            "Capital expenditure share can rise simply because revenue expenditure (pensions, "
            "salaries) is held flat - check the absolute capex trend, not just the ratio.",
            "Multi-year procurement contracts create lumpy year-to-year capex figures.",
        ),
        calculation="defence_capital_expenditure / nominal_gdp * 100",
        data_points=("defence_capital_expenditure_rs_cr", "nominal_gdp_rs_cr"),
        proxy_based=False,
        chart_type="line",
        tier="B",
    ),
    KPISpec(
        ministry_code="DEF",
        key="domestic_mic_development",
        name="Domestic MIC Development",
        definition="Share of the defence capital-acquisition (equipment-buying) budget spent with domestic suppliers rather than foreign ones. Value of domestic defence production is carried as the secondary series.",
        data_quality="MEDIUM",
        source_name="Ministry of Defence / Department of Defence Production annual reports + PIB; Standing Committee on Defence reports",
        source_url="https://www.mod.gov.in/",
        update_frequency="Annual",
        time_period="FY 2014-15 onwards",
        units="% of procurement",
        caveats=(
            "Official 'indigenisation' figures count domestic assembly / licensed production of "
            "foreign-designed platforms as indigenous - this materially overstates true design/IP "
            "self-reliance. Any AI commentary MUST flag this measurement gap explicitly.",
            "The procurement-budget share is not independently audited and can be met by re-timing "
            "which contracts fall in a given year.",
        ),
        calculation="domestic_capital_procurement_rs_cr / total_capital_procurement_rs_cr * 100 (as officially reported)",
        data_points=("domestic_capital_procurement_rs_cr", "total_capital_procurement_rs_cr", "domestic_production_value_rs_cr"),
        proxy_based=True,
        chart_type="line",
        tier="B",
    ),
    KPISpec(
        ministry_code="DEF",
        key="force_modernisation",
        name="Force Modernisation",
        definition="Rough share of major platforms rated 'current' or 'state-of-the-art' rather than 'vintage', against the armed forces' own doctrine of roughly one-third each. Capital-acquisition budget utilisation is carried as the secondary series.",
        data_quality="LOW",
        source_name="Standing Committee on Defence reports; service-headquarters vintage/current/state-of-the-art disclosures",
        source_url="https://www.mod.gov.in/",
        update_frequency="Annual",
        time_period="FY 2014-15 onwards",
        units="% of fleet modern",
        caveats=(
            "The vintage/current/state-of-the-art split is self-reported by the services and not "
            "independently audited - treat as a claim rather than a verified fact.",
            "Fleet composition (numbers of each platform) is not disclosed alongside the percentages, "
            "so a stable % can mask an ageing or shrinking absolute fleet - e.g. IAF fighter "
            "squadron strength remains below the sanctioned 42.",
        ),
        calculation="100 - vintage_share_pct (as disclosed to Parliament); no single official formula exists",
        data_points=("modern_equipment_share_pct", "capital_budget_utilisation_pct"),
        proxy_based=True,
        chart_type="line",
        tier="B",
    ),
]

# ---------------------------------------------------------------------------
# MINISTRY 8: EDUCATION (EDU)
# ---------------------------------------------------------------------------

_EDUCATION = [
    KPISpec(
        ministry_code="EDU",
        key="learning_outcomes",
        name="Learning Outcomes",
        definition="Share of children enrolled in Class 3 (rural) who can read a Class 2 level text, from ASER. The government NAS Grade-3 language proficiency figure is carried as the secondary series.",
        data_quality="HIGH",
        source_name="ASER Centre / Pratham annual rural household survey; National Achievement Survey (NCERT / Ministry of Education)",
        source_url="https://asercentre.org/",
        update_frequency="ASER roughly biennial (rural) / NAS periodic (national)",
        time_period="2014 onwards",
        units="% of Class 3 children",
        caveats=(
            "ASER covers rural India only - do not generalise to urban outcomes.",
            "ASER field reading rounds were not run every year (and ASER 2021 was phone-based and "
            "not comparable); interpolated years are flagged 'Estimated'.",
            "Recovery must be judged against both the pre-COVID level (27.2% in 2018) and the "
            "absolute level - 23% of Class 3 children reading at Class 2 level is still low.",
        ),
        calculation="children_in_Std_III_reading_Std_II_text / children_in_Std_III_assessed * 100",
        data_points=("aser_std3_can_read_std2_pct", "nas_grade3_language_pct"),
        proxy_based=False,
        chart_type="line",
        tier="B",
    ),
    KPISpec(
        ministry_code="EDU",
        key="exam_integrity",
        name="Exam Integrity",
        definition="Count of major documented paper leaks or exam cancellations in national and state board, entrance and recruitment examinations each year. Approximate number of aspirants affected is carried as the secondary series.",
        data_quality="LOW",
        source_name="Compiled from national press reporting; Parliament replies where available; the Public Examinations (Prevention of Unfair Means) Act 2024",
        source_url="https://www.education.gov.in/",
        update_frequency="Annual (best-effort compilation)",
        time_period="FY 2014-15 onwards",
        units="incidents / year",
        caveats=(
            "There is no official register of exam-integrity incidents - the counts are compiled "
            "from press reporting and are indicative of the trend, not exact.",
            "'Major' is a judgement call; a year with one huge leak (e.g. NEET-UG 2024) affecting "
            "millions is not equivalent to a year with several small state-exam leaks.",
            "PROXY STATUS: any AI commentary must call this a 'best available proxy' and never an "
            "official metric.",
        ),
        calculation="count of major documented paper-leak / cancellation incidents in the year",
        data_points=("major_leak_or_cancellation_incidents", "aspirants_affected_lakh"),
        proxy_based=True,
        chart_type="line",
        tier="C",
    ),
    KPISpec(
        ministry_code="EDU",
        key="enrollment_quality",
        name="Enrollment Quality",
        definition="Gross Enrolment Ratio for senior secondary (Classes 11-12) from UDISE+ - enrolment in Classes 11-12 as a % of the 16-17 age group. Elementary pupil-teacher ratio is carried as the secondary series.",
        data_quality="MEDIUM",
        source_name="UDISE+ (Unified District Information System for Education Plus), Ministry of Education",
        source_url="https://udiseplus.gov.in/",
        update_frequency="Annual",
        time_period="FY 2014-15 onwards",
        units="% GER (Class 11-12)",
        caveats=(
            "GER can exceed 100 where over- or under-age children are enrolled; senior-secondary "
            "GER well below 100 mainly reflects drop-out before Class 11.",
            "UDISE+ moved to an individual student-record (headcount) method from 2021-22, which "
            "lowered reported totals - the pre- and post-2021-22 points are not strictly comparable.",
        ),
        calculation="enrolment_classes_11_12 / population_aged_16_17 * 100",
        data_points=("ger_senior_secondary_pct", "pupil_teacher_ratio_elementary"),
        proxy_based=False,
        chart_type="line",
        tier="B",
    ),
]

# ---------------------------------------------------------------------------
# MINISTRY 9: SKILL DEVELOPMENT & ENTREPRENEURSHIP (SKILL)
# ---------------------------------------------------------------------------

_SKILL_DEVELOPMENT = [
    KPISpec(
        ministry_code="SKILL",
        key="youth_neet_rate",
        name="Youth NEET Rate",
        definition="% of youth Not in Employment, Education, or Training (NEET), benchmarked against a 2014 baseline.",
        data_quality="MEDIUM",
        source_name="Periodic Labour Force Survey (PLFS), MoSPI",
        source_url="https://mospi.gov.in/",
        update_frequency="Annual (PLFS annual bulletin)",
        time_period="FY 2017-18 onwards (PLFS methodology start), benchmarked to a 2014 baseline",
        units="%",
        caveats=(
            "Pre-PLFS unemployment/NEET series (older NSSO rounds) use a different survey design and "
            "are not strictly comparable - treat FY2017-18 as a methodology break.",
            "NEET rate conflates genuinely idle youth with those in unpaid family work or informal "
            "learning not captured by the survey's education/training categories.",
        ),
        calculation="youth_neet_count / total_youth_population * 100 (15-29 age group, usual status)",
        data_points=("youth_neet_count", "total_youth_population"),
        proxy_based=False,
        chart_type="line",
        tier="B",
    ),
    KPISpec(
        ministry_code="SKILL",
        key="apprenticeship_utilisation",
        name="Apprenticeship Utilisation",
        definition="Actual apprenticeship-scheme expenditure (NAPS + NATS) as a % of the year's budget allocation. Rupee allocation is carried as the secondary series.",
        data_quality="MEDIUM",
        source_name="Union Budget / Outcome Budget (MSDE) - apprenticeship allocation vs actual expenditure; Standing Committee on Labour reports",
        source_url="https://www.msde.gov.in/",
        update_frequency="Annual",
        time_period="FY 2016-17 onwards (scheme scale-up)",
        units="% of budget used",
        caveats=(
            "Budget utilisation measures spend, not outcomes - pair with placement / certification "
            "rates before calling high utilisation a success.",
            "Apprenticeship budgets have historically been under-spent by large margins; the Standing "
            "Committee on Labour has repeatedly flagged this.",
        ),
        calculation="apprenticeship_actual_expenditure_rs_cr / apprenticeship_budget_allocation_rs_cr * 100",
        data_points=("apprentice_actual_spend_rs_cr", "apprentice_budget_allocation_rs_cr"),
        proxy_based=False,
        chart_type="line",
        tier="B",
    ),
    KPISpec(
        ministry_code="SKILL",
        key="job_creation",
        name="Job Creation",
        definition="Net new formal-sector jobs, proxied by net EPFO subscriber additions.",
        data_quality="MEDIUM",
        source_name="EPFO payroll data (net subscriber addition series)",
        source_url="https://epfindia.gov.in/",
        update_frequency="Monthly",
        time_period="FY 2017-18 onwards (EPFO payroll series start)",
        units="Lakh formal jobs/yr",
        caveats=(
            "EPFO net additions is a PROXY for formal job creation - it also captures formalisation "
            "of existing jobs (employers newly complying) and job switching (re-registration), not "
            "only genuinely new jobs. State this explicitly whenever cited.",
        ),
        calculation="new_epfo_subscribers - exits, as published by EPFO",
        data_points=("epfo_net_subscriber_additions",),
        proxy_based=True,
        chart_type="line",
        tier="B",
    ),
]

# ---------------------------------------------------------------------------
# MINISTRY 10: ROAD TRANSPORT & HIGHWAYS (ROAD)
# ---------------------------------------------------------------------------

_ROAD_TRANSPORT = [
    KPISpec(
        ministry_code="ROAD",
        key="logistics_cost_pct",
        name="Logistics Cost %",
        definition="Total national logistics cost as a % of GDP.",
        data_quality="MEDIUM",
        source_name="Ministry of Commerce & Industry / NITI Aayog logistics cost estimates",
        source_url="https://morth.nic.in/",
        update_frequency="Annual",
        time_period="FY 2014-15 onwards",
        units="% of GDP",
        caveats=(
            "There is no single official, continuously-published logistics-cost-to-GDP series; "
            "published figures vary by estimation methodology across studies (NITI Aayog, World "
            "Bank, industry bodies) - cite the specific source and don't blend series.",
        ),
        calculation="total_logistics_cost / nominal_gdp * 100 (methodology varies by source)",
        data_points=("total_logistics_cost_rs_cr", "nominal_gdp_rs_cr"),
        proxy_based=True,
        chart_type="line",
        tier="B",
    ),
    KPISpec(
        ministry_code="ROAD",
        key="highway_construction",
        name="Highway Construction",
        definition="Km of national highway constructed per day, annual average, against a pace benchmark.",
        data_quality="HIGH",
        source_name="Ministry of Road Transport & Highways (MoRTH) / NHAI physical progress reports",
        source_url="https://morth.nic.in/",
        update_frequency="Monthly (MoRTH publishes a running km/day figure)",
        time_period="FY 2014-15 onwards",
        units="km/day",
        caveats=(
            "'Constructed' figures sometimes mix new construction with widening/upgrade of existing "
            "roads - check the MoRTH footnote definition for the year before comparing across years.",
        ),
        calculation="total_km_constructed_in_year / days_in_year",
        data_points=("total_km_constructed", "reporting_period_days"),
        proxy_based=False,
        chart_type="bar",
        tier="B",
    ),
    KPISpec(
        ministry_code="ROAD",
        key="modal_share",
        name="Modal Share",
        definition="Road's share of total inland freight movement (tonne-km). Rail's share is carried as the secondary series.",
        data_quality="MEDIUM",
        source_name="NITI Aayog freight-mode studies + MoRTH + Indian Railways (rail comparison)",
        source_url="https://morth.nic.in/",
        update_frequency="Annual",
        time_period="FY 2014-15 onwards",
        units="% of freight tonne-km",
        caveats=(
            "Road and rail freight are measured by different agencies with different methodologies "
            "- these shares are not from a single reconciled national freight survey.",
            "A high road share is not a road-sector 'failure' per se - national policy wants freight "
            "rebalanced toward cheaper, cleaner rail and waterways, which is why higher_is_better is "
            "False for this KPI.",
        ),
        calculation="road_freight_tonne_km / total_inland_freight_tonne_km * 100",
        data_points=("road_share_pct", "rail_share_pct", "other_share_pct"),
        proxy_based=True,
        chart_type="line",
        tier="B",
    ),
]

ALL_KPI_SPECS: list[KPISpec] = (
    _FINANCE
    + _PETROLEUM
    + _AGRICULTURE
    + _RAILWAYS
    + _POWER
    + _COMMERCE
    + _DEFENCE
    + _EDUCATION
    + _SKILL_DEVELOPMENT
    + _ROAD_TRANSPORT
)

assert len(ALL_KPI_SPECS) == 30, f"expected 30 KPI specs, got {len(ALL_KPI_SPECS)}"

_BY_MINISTRY: dict[str, list[KPISpec]] = {}
_BY_MINISTRY_AND_NAME: dict[tuple[str, str], KPISpec] = {}
for _spec in ALL_KPI_SPECS:
    _BY_MINISTRY.setdefault(_spec.ministry_code, []).append(_spec)
    _BY_MINISTRY_AND_NAME[(_spec.ministry_code, _spec.name)] = _spec


def get_specs_for_ministry(ministry_code: str) -> list[KPISpec]:
    return list(_BY_MINISTRY.get(ministry_code, []))


def get_kpi_spec(ministry_code: str, kpi_name: str) -> KPISpec | None:
    """Look up by exact KPI name first; fall back to a loose substring/keyword
    match since dashboard KPI names may be phrased slightly differently from
    the spec's canonical `name`."""
    spec = _BY_MINISTRY_AND_NAME.get((ministry_code, kpi_name))
    if spec is not None:
        return spec
    for spec in _BY_MINISTRY.get(ministry_code, []):
        if spec.name.lower() in kpi_name.lower() or kpi_name.lower() in spec.name.lower():
            return spec
    return None


def get_spec_by_key(key: str) -> KPISpec | None:
    for spec in ALL_KPI_SPECS:
        if spec.key == key:
            return spec
    return None


# Every ministry now runs on a real, provenance-tracked curated data layer:
# Tier-A -> data/tier_a/ (app.tier_a_pipeline); Tier-B -> data/tier_b/ (app.tier_b_pipeline).
TIER_A_MINISTRIES = ("PETRO", "AGRI", "FIN", "RAIL", "POW")
TIER_B_MINISTRIES = ("COMM", "DEF", "EDU", "SKILL", "ROAD")
TIER_C_KEYS = tuple(s.key for s in ALL_KPI_SPECS if s.tier == "C")
