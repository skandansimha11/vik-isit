"""Backwards-compatible shim - real connector is ``app.connectors.tier_a.power``."""

from app.connectors.tier_a.power import PowerConnector, get_power_connector

__all__ = ["PowerConnector", "get_power_connector"]
