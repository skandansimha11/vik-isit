"""Backwards-compatible shim — real connector is ``app.connectors.tier_a.agriculture``."""

from app.connectors.tier_a.agriculture import AgricultureConnector, get_agriculture_connector

__all__ = ["AgricultureConnector", "get_agriculture_connector"]
