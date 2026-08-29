"""The 15 Tier-A KPIs: canonical definition, plain-language framing, chart shape,
and targets (official / near-term + aspirational / structural).

``key`` matches ``app/kpi_specifications.py``; ``name`` matches
``app/seed_dashboard.py``. ``display_title`` is the layman heading shown on the
card; ``name`` is kept as the small technical subtitle. Charts are deliberately
kept to a single primary series + target lines — secondary metrics (GRM, the
ACS-ARR gap, ethanol volume, congestion, YoY growth, forex savings) are computed
and surfaced in the data table / provenance panel, not as a second chart axis.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TierAkpiTarget:
    official: float | None
    aspirational: float | None
    official_label: str = "Official / near-term target"
    aspirational_label: str = "Aspirational / structural level"


@dataclass(frozen=True)
class TierAKpi:
    ministry_code: str
    key: str
    name: str
    display_title: str
    plain_note: str
    unit: str
    data_shape: str  # time_line | time_breakdown
    chart_type: str  # line | stacked_area
    higher_is_better: bool
    valid_range: tuple[float, float]
    data_quality: str  # HIGH | MEDIUM | LOW
    is_proxy: bool
    source_name: str
    source_url: str
    cadence: str
    datasets: tuple[str, ...]
    target: TierAkpiTarget
    secondary_label: str | None = None
    secondary_unit: str | None = None
    breakdown_label: str | None = None
    breakdown_keys: tuple[str, ...] = ()
    period_kind: str = "fiscal_year"

    # ---- compatibility shims for code that still reads the flat fields ----
    @property
    def target_value(self) -> float | None:
        return self.target.official

    @property
    def aspirational_target(self) -> float | None:
        return self.target.aspirational

    @property
    def benchmark_label(self) -> str:
        return self.target.official_label


_ANALYTICAL = "Analytical / desirable level"


_FINANCE = [
    TierAKpi(
        ministry_code="FIN",
        key="fiscal_deficit_pct_gdp",
        name="Fiscal Deficit",
        display_title="Government Budget Gap",
        plain_note="How much more the central government spends than it earns in a year, measured as a share of the whole economy. Lower is healthier.",
        unit="% of GDP",
        data_shape="time_line",
        chart_type="line",
        higher_is_better=False,
        valid_range=(0.0, 15.0),
        data_quality="HIGH",
        is_proxy=False,
        source_name="Union Budget (Budget at a Glance) + Economic Survey Statistical Appendix + CGA",
        source_url="https://www.indiabudget.gov.in/",
        cadence="Annual (FY); monthly actuals via CGA",
        datasets=("fiscal",),
        target=TierAkpiTarget(4.3, 3.0, "FRBM glide-path (FY27 BE ~4.3%)", "Long-run sustainable (~3%)"),
    ),
    TierAKpi(
        ministry_code="FIN",
        key="tax_administration_intensity",
        name="Tax Harassment Cases",
        display_title="Tax Notices & Disputes",
        plain_note="How heavy-handed tax administration is — proxied by the number of tax appeals stuck in the system (Commissioner, Tribunal and High Court combined). Scrutiny and reassessment-notice counts are in the table. No official 'harassment index' exists.",
        unit="'000 appeals pending",
        data_shape="time_line",
        chart_type="line",
        higher_is_better=False,
        valid_range=(0.0, 2000.0),
        data_quality="LOW",
        is_proxy=True,
        source_name="CBDT Annual Report + Direct Taxes Time-Series + CAG audit reports + Parliament replies",
        source_url="https://incometaxindia.gov.in/Pages/Direct-Taxes-Data.aspx",
        cadence="Annual (occasional parliamentary updates)",
        datasets=("tax_admin",),
        target=TierAkpiTarget(None, None, "No hard target — lower is better", "Faster disposal, fewer disproportionate notices"),
        secondary_label="Scrutiny + reassessment notices",
        secondary_unit="'000",
    ),
    TierAKpi(
        ministry_code="FIN",
        key="tax_collection_growth",
        name="Tax Collection Growth",
        display_title="Tax Revenue (Share of GDP)",
        plain_note="Central government tax collection as a share of the economy. Rising means the tax base is genuinely broadening, not just riding inflation. Year-on-year growth is in the table.",
        unit="% of GDP",
        data_shape="time_line",
        chart_type="line",
        higher_is_better=True,
        valid_range=(6.0, 16.0),
        data_quality="HIGH",
        is_proxy=False,
        source_name="CBDT Direct Taxes Data + Union Budget Receipt Budget + Economic Survey",
        source_url="https://incometaxindia.gov.in/Pages/Direct-Taxes-Data.aspx",
        cadence="Monthly (provisional) / Annual (final)",
        datasets=("tax_revenue",),
        target=TierAkpiTarget(12.0, 13.0, "Gross Tax-to-GDP ~12%", "Structural 12-13% with tax buoyancy > 1.2"),
        secondary_label="Gross Tax Revenue growth",
        secondary_unit="% YoY",
    ),
]

_PETROLEUM = [
    TierAKpi(
        ministry_code="PETRO",
        key="oil_import_dependence",
        name="Oil Import Dependence",
        display_title="Reliance on Imported Oil",
        plain_note="Share of India's petroleum needs (crude + products) met by imports rather than domestic production. Driven mostly by global prices and demand growth — not policy alone.",
        unit="% of consumption",
        data_shape="time_line",
        chart_type="line",
        higher_is_better=False,
        valid_range=(50.0, 100.0),
        data_quality="HIGH",
        is_proxy=False,
        source_name="PPAC — Snapshot of India's Oil & Gas Data / Ready Reckoner",
        source_url="https://ppac.gov.in/",
        cadence="Monthly",
        datasets=("crude",),
        target=TierAkpiTarget(85.0, 80.0, "Reduce below ~85%", "Structural decline toward ~80%"),
    ),
    TierAKpi(
        ministry_code="PETRO",
        key="ethanol_blending",
        name="Ethanol Blending %",
        display_title="Ethanol Blended into Petrol",
        plain_note="Average share of ethanol mixed into petrol sold nationally, by Ethanol Supply Year. India reached the 20% (E20) goal ahead of the 2025-26 schedule. Volume blended is in the table.",
        unit="% blend",
        data_shape="time_line",
        chart_type="line",
        higher_is_better=True,
        valid_range=(0.0, 30.0),
        data_quality="HIGH",
        is_proxy=False,
        source_name="PPAC — Ethanol Blended Petrol (EBP) Programme / Ready Reckoner",
        source_url="https://ppac.gov.in/",
        cadence="Monthly (Ethanol Supply Year basis)",
        datasets=("ethanol",),
        target=TierAkpiTarget(20.0, 25.0, "E20 (achieved)", "Maintain E20; higher blends only after readiness"),
        secondary_label="Ethanol volume blended",
        secondary_unit="crore L",
        period_kind="supply_year",
    ),
    TierAKpi(
        ministry_code="PETRO",
        key="refining_efficiency",
        name="Refining Efficiency",
        display_title="Refinery Capacity in Use",
        plain_note="How hard India's oil refineries run versus their installed capacity (India routinely runs above 100%). The gross refining margin ($/bbl) — which mostly tracks global oil prices — is in the table.",
        unit="% capacity used",
        data_shape="time_line",
        chart_type="line",
        higher_is_better=True,
        valid_range=(60.0, 130.0),
        data_quality="MEDIUM",
        is_proxy=False,
        source_name="PPAC Ready Reckoner (refining) + PPAC refinery performance",
        source_url="https://ppac.gov.in/",
        cadence="Monthly",
        datasets=("refining",),
        target=TierAkpiTarget(100.0, None, "Full capacity utilisation", _ANALYTICAL + " (~100-105% + healthy margins)"),
        secondary_label="Gross refining margin",
        secondary_unit="$/bbl",
    ),
]

_AGRICULTURE = [
    TierAKpi(
        ministry_code="AGRI",
        key="real_farmer_income",
        name="Real Farmer Income",
        display_title="Farm Incomes, Inflation-Adjusted",
        plain_note="A proxy for real farm-sector earnings: agriculture & allied output per worker at constant prices, indexed to 2014 = 100. This tracks sector productivity, NOT household take-home pay — direct surveys (NSS SAS, NABARD NAFIS) give a more mixed picture.",
        unit="index (2014=100)",
        data_shape="time_line",
        chart_type="line",
        higher_is_better=True,
        valid_range=(70.0, 260.0),
        data_quality="MEDIUM",
        is_proxy=True,
        source_name="MoSPI National Accounts (agri & allied GVA, constant prices) + PLFS/Census workforce + NSS SAS 2013/2019 + NABARD NAFIS 2016-17/2021-22",
        source_url="https://www.mospi.gov.in/",
        cadence="Annual",
        datasets=("farmer_income",),
        target=TierAkpiTarget(200.0, 230.0, "Doubling real income (2016 goal)", "Sustained 4-5% real growth + rising yields"),
    ),
    TierAKpi(
        ministry_code="AGRI",
        key="ethanol_programme_agri",
        name="Ethanol Programme",
        display_title="Ethanol Supplied by Farm Sector",
        plain_note="Volume of ethanol (from sugarcane and grain) blended into petrol each supply year. Government-claimed foreign-exchange savings are in the table — these estimates typically ignore the opportunity cost of the feedstock.",
        unit="crore L",
        data_shape="time_line",
        chart_type="line",
        higher_is_better=True,
        valid_range=(0.0, 2000.0),
        data_quality="HIGH",
        is_proxy=False,
        source_name="PPAC — EBP Programme + MoP&NG / PIB (forex-saving estimates)",
        source_url="https://ppac.gov.in/",
        cadence="Monthly / Annual (Ethanol Supply Year)",
        datasets=("ethanol",),
        target=TierAkpiTarget(1016.0, 1200.0, "E20-equivalent volume", "Expand only if full cost-benefit stays positive"),
        secondary_label="Claimed forex savings",
        secondary_unit="₹'000 Cr",
        period_kind="supply_year",
    ),
    TierAKpi(
        ministry_code="AGRI",
        key="food_inflation",
        name="Food Inflation",
        display_title="Food Price Inflation",
        plain_note="Year-on-year rise in food & beverage prices (CPI), averaged over the fiscal year. Heavily weather- and monsoon-driven in the short run.",
        unit="% CPI Food YoY",
        data_shape="time_line",
        chart_type="line",
        higher_is_better=False,
        valid_range=(-5.0, 20.0),
        data_quality="HIGH",
        is_proxy=False,
        source_name="MoSPI — CPI (Food & Beverages) press releases; RBI DBIE",
        source_url="https://www.mospi.gov.in/",
        cadence="Monthly",
        datasets=("cpi_food",),
        target=TierAkpiTarget(4.0, 3.0, "Low and stable (~4%, RBI mid-point)", "Average 3-5% over the cycle"),
        period_kind="month",
    ),
]

_RAILWAYS = [
    TierAKpi(
        ministry_code="RAIL",
        key="freight_volume_growth",
        name="Freight Volume Growth",
        display_title="Rail Freight Growth",
        plain_note="Year-on-year growth in the tonnage of goods loaded onto the railways. Needs to run ahead of GDP growth for rail to gain share from road. Absolute tonnage and net-tonne-km are in the table.",
        unit="% YoY",
        data_shape="time_line",
        chart_type="line",
        higher_is_better=True,
        valid_range=(-30.0, 30.0),
        data_quality="HIGH",
        is_proxy=False,
        source_name="Indian Railways Year Book / Statistical Statements + PIB monthly freight-loading releases",
        source_url="https://indianrailways.gov.in/",
        cadence="Monthly (provisional) / Annual (final)",
        datasets=("freight",),
        target=TierAkpiTarget(8.0, 10.0, "~8% (viability floor)", "Sustained 8-10% a year"),
    ),
    TierAKpi(
        ministry_code="RAIL",
        key="rail_market_share",
        name="Rail Market Share",
        display_title="Freight: Rail vs Road",
        plain_note="Share of India's goods movement (tonne-km) carried by rail versus road and other modes. Rail's share has structurally declined for decades; the National Rail Plan targets 45% by 2030.",
        unit="% of freight tonne-km",
        data_shape="time_breakdown",
        chart_type="stacked_area",
        higher_is_better=True,
        valid_range=(0.0, 100.0),
        data_quality="MEDIUM",
        is_proxy=False,
        source_name="Indian Railways + MoRTH + NITI Aayog / DPIIT-NCAER & NTDPC freight-mode studies",
        source_url="https://indianrailways.gov.in/",
        cadence="Annual",
        datasets=("modal_share",),
        target=TierAkpiTarget(40.0, 45.0, "National Rail Plan ~40%", "45% of freight tonne-km by 2030"),
        breakdown_label="Mode",
        breakdown_keys=("Rail", "Road", "Other"),
    ),
    TierAKpi(
        ministry_code="RAIL",
        key="train_speeds_capacity",
        name="Train Speeds & Capacity",
        display_title="Freight Train Speed",
        plain_note="Average speed of goods trains across the network (the COVID year is a one-off outlier — near-empty tracks). Congested-route share and electrification are in the table.",
        unit="km/h",
        data_shape="time_line",
        chart_type="line",
        higher_is_better=True,
        valid_range=(15.0, 90.0),
        data_quality="MEDIUM",
        is_proxy=True,
        source_name="Indian Railways Year Book / Annual Report + FOIS + PIB",
        source_url="https://indianrailways.gov.in/",
        cadence="Annual",
        datasets=("speed_capacity",),
        target=TierAkpiTarget(40.0, 50.0, "Higher speeds on DFCs", "50+ km/h on key corridors"),
        secondary_label="Congested-route share",
        secondary_unit="%",
    ),
]

_POWER = [
    TierAKpi(
        ministry_code="POW",
        key="industrial_tariffs",
        name="Industrial Tariffs",
        display_title="Factory Electricity Prices",
        plain_note="Average electricity tariff paid by industrial (HT/LT) consumers — national average plus four large industrial states. High tariffs (from cross-subsidy of farm and household users) hurt manufacturing competitiveness.",
        unit="₹/kWh",
        data_shape="time_breakdown",
        chart_type="line",
        higher_is_better=False,
        valid_range=(2.0, 15.0),
        data_quality="MEDIUM",
        is_proxy=False,
        source_name="CEA — All-India Electricity Statistics / tariff compilations + PFC + SERC tariff orders",
        source_url="https://cea.nic.in/",
        cadence="Annual (tariff-order cycle)",
        datasets=("industrial_tariffs",),
        target=TierAkpiTarget(7.0, 6.0, "Cost-reflective (~₹7/kWh)", "Among the more competitive in Asia (~₹6/kWh)"),
        breakdown_label="State",
        breakdown_keys=("National avg", "Maharashtra", "Gujarat", "Tamil Nadu", "Uttar Pradesh"),
    ),
    TierAKpi(
        ministry_code="POW",
        key="discom_financial_health",
        name="Discom Financial Health",
        display_title="Electricity Lost or Unpaid",
        plain_note="Share of electricity that distribution utilities send out but never get paid for — through technical losses, theft and unbilled supply (AT&C losses). The cost-vs-revenue gap (ACS–ARR) and accumulated losses are in the table.",
        unit="% AT&C loss",
        data_shape="time_line",
        chart_type="line",
        higher_is_better=False,
        valid_range=(5.0, 45.0),
        data_quality="HIGH",
        is_proxy=False,
        source_name="Power Finance Corporation — Report on Performance of Power Utilities",
        source_url="https://www.pfcindia.com/",
        cadence="Annual",
        datasets=("discom",),
        target=TierAkpiTarget(15.0, 8.0, "12-15% by end of RDSS (~2028)", "Single-digit nationally"),
        secondary_label="ACS-ARR gap",
        secondary_unit="₹/kWh",
    ),
    TierAKpi(
        ministry_code="POW",
        key="power_availability",
        name="Power Availability",
        display_title="Electricity Demand Met",
        plain_note="Share of the country's electricity demand that was actually supplied (100% minus the energy shortfall). Rural vs urban hours of supply are in the table — national averages hide large gaps.",
        unit="% of demand met",
        data_shape="time_line",
        chart_type="line",
        higher_is_better=True,
        valid_range=(85.0, 100.0),
        data_quality="MEDIUM",
        is_proxy=False,
        source_name="CEA — Power Supply Position / Load Generation Balance Report (LGBR)",
        source_url="https://cea.nic.in/",
        cadence="Monthly / Annual",
        datasets=("reliability",),
        target=TierAkpiTarget(99.5, 100.0, "Near-zero energy deficit", "100% demand met, including rural"),
    ),
]

TIER_A_KPIS: list[TierAKpi] = _FINANCE + _PETROLEUM + _AGRICULTURE + _RAILWAYS + _POWER
assert len(TIER_A_KPIS) == 15, f"expected 15 Tier-A KPIs, got {len(TIER_A_KPIS)}"

TIER_A_BY_KEY: dict[str, TierAKpi] = {k.key: k for k in TIER_A_KPIS}
TIER_A_BY_NAME: dict[tuple[str, str], TierAKpi] = {(k.ministry_code, k.name): k for k in TIER_A_KPIS}
TIER_A_MINISTRIES: tuple[str, ...] = ("FIN", "PETRO", "AGRI", "RAIL", "POW")
