"""Ministry of Commerce & Industry - Tier-B connector.

KPIs:
  * industrial_import_dependence - net industrial-goods imports as % of demand (proxy)
  * manufacturing_growth         - manufacturing GVA as % of total GVA
  * pli_effectiveness            - investment realised as % of PLI commitments (proxy)
"""

from __future__ import annotations

from app.connectors.tier_b.base import TierBConnector


class CommerceConnector(TierBConnector):
    ministry_code = "COMM"
    dataset_files = {
        "import_dependence": "commerce/import_dependence.csv",
        "manufacturing": "commerce/manufacturing.csv",
        "pli": "commerce/pli.csv",
    }
    valid_ranges = {
        "Industrial Imports %": (0.0, 40.0),
        "Manufacturing Growth": (10.0, 30.0),
        "PLI Effectiveness": (0.0, 120.0),
    }

    def _compute_industrial_import_dependence(self, spec):
        return self._simple_series(
            spec,
            "import_dependence",
            "net_import_dependence_pct",
            formula="net industrial-goods imports (non-oil, non-gold manufactured + intermediate) / domestic consumption * 100 ; consumption = production + imports - exports",
            secondary_col="net_trade_balance_usd_bn",
        )

    def _compute_manufacturing_growth(self, spec):
        return self._simple_series(
            spec,
            "manufacturing",
            "manufacturing_gva_share_pct",
            formula="manufacturing GVA (current prices) / total GVA (current prices) * 100 ; secondary = YoY growth of IIP-manufacturing",
            secondary_col="iip_manufacturing_growth_pct",
        )

    def _compute_pli_effectiveness(self, spec):
        return self._simple_series(
            spec,
            "pli",
            "investment_realised_pct",
            formula="cumulative investment realised under PLI schemes / cumulative investment committed * 100 (company self-reported)",
            secondary_col="investment_realised_rs_000cr",
        )


def get_commerce_connector() -> CommerceConnector:
    return CommerceConnector()
