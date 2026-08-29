from __future__ import annotations

from app.connectors.base import BaseConnector
from app.connectors.csv_connector import CSVConnector
from app.connectors.excel_connector import ExcelConnector
from app.connectors.pdf_connector import PDFConnector
from app.connectors.web_connector import WebConnector

# Generic document connectors. The five Tier-A ministry KPIs are computed by
# app.connectors.tier_a (source_type "tier_a"), handled directly in
# app.pipeline.sync_service — they do not go through this registry.
_CONNECTORS: dict[str, BaseConnector] = {
    "csv": CSVConnector(),
    "excel": ExcelConnector(),
    "pdf": PDFConnector(),
    "web": WebConnector(),
}


def get_connector(source_type: str) -> BaseConnector:
    try:
        return _CONNECTORS[source_type]
    except KeyError:
        raise ValueError(
            f"Unknown source type '{source_type}'. Expected one of: {sorted(_CONNECTORS)}"
        )
