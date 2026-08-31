"""Ministry of Defence - Tier-B connector.

KPIs:
  * defence_capex             - defence capital outlay as % of GDP
  * domestic_mic_development  - % of procurement spent with Indian industry (proxy)
  * force_modernisation       - modern / current share of major equipment (proxy)
"""

from __future__ import annotations

from app.connectors.tier_b.base import TierBConnector


class DefenceConnector(TierBConnector):
    ministry_code = "DEF"
    dataset_files = {
        "capex": "defence/capex.csv",
        "indigenisation": "defence/indigenisation.csv",
        "modernisation": "defence/modernisation.csv",
    }
    valid_ranges = {
        "Defence CapEx": (0.2, 2.0),
        "Domestic MIC Development": (20.0, 100.0),
        "Force Modernisation": (30.0, 100.0),
    }

    def _compute_defence_capex(self, spec):
        return self._simple_series(
            spec,
            "capex",
            "capital_outlay_pct_gdp",
            formula="defence Services capital outlay / nominal GDP * 100",
            secondary_col="capital_outlay_rs_000cr",
        )

    def _compute_domestic_mic_development(self, spec):
        return self._simple_series(
            spec,
            "indigenisation",
            "domestic_procurement_share_pct",
            formula="capital-acquisition budget spent with Indian vendors / total capital-acquisition budget * 100 (licensed/assembled production counts as domestic)",
            secondary_col="domestic_production_value_rs_000cr",
        )

    def _compute_force_modernisation(self, spec):
        return self._simple_series(
            spec,
            "modernisation",
            "modern_equipment_share_pct",
            formula="share of major platforms rated 'current' or 'state-of-the-art' (vs 'vintage'), as disclosed to the Standing Committee on Defence",
            secondary_col="capital_budget_utilisation_pct",
        )


def get_defence_connector() -> DefenceConnector:
    return DefenceConnector()
