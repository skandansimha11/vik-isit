from __future__ import annotations

import io
from typing import Any

import pandas as pd
from bs4 import BeautifulSoup

from app.connectors.base import BaseConnector


class WebConnector(BaseConnector):
    """Scrapes either a single labeled stat (via CSS `selector`) or a
    table (via `table_index`, pandas.read_html) from an HTML page."""

    source_type = "web"

    def parse(self, raw: bytes, config: dict[str, Any]) -> list[dict[str, Any]]:
        html = raw.decode(config.get("encoding", "utf-8"), errors="ignore")

        if "selector" in config:
            soup = BeautifulSoup(html, "html.parser")
            el = soup.select_one(config["selector"])
            value = el.get_text(strip=True) if el else None
            return [{"label": config.get("metric_label", ""), "value": value}]

        table_index = config.get("table_index", 0)
        tables = pd.read_html(io.StringIO(html))
        if not tables or table_index >= len(tables):
            return []
        return tables[table_index].to_dict(orient="records")
