"""Backwards-compatible shim — real connector is ``app.connectors.tier_a.finance``."""

from app.connectors.tier_a.finance import FinanceConnector, get_finance_connector

__all__ = ["FinanceConnector", "get_finance_connector"]
