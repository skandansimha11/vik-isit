"""Backwards-compatible shim — real connector is ``app.connectors.tier_a.railways``."""

from app.connectors.tier_a.railways import RailwaysConnector, get_railways_connector

__all__ = ["RailwaysConnector", "get_railways_connector"]
