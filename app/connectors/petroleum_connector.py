"""Backwards-compatible shim.

The real, provenance-tracked Petroleum connector now lives in
``app.connectors.tier_a.petroleum``. This module re-exports it so existing
imports (and the test-suite) keep working.
"""

from app.connectors.tier_a.petroleum import PetroleumConnector, get_petroleum_connector

__all__ = ["PetroleumConnector", "get_petroleum_connector"]
