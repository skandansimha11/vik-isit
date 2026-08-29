from __future__ import annotations

import csv
import io
from typing import Any

from app.connectors.base import BaseConnector


class CSVConnector(BaseConnector):
    source_type = "csv"

    def parse(self, raw: bytes, config: dict[str, Any]) -> list[dict[str, Any]]:
        text = raw.decode(config.get("encoding", "utf-8-sig"))
        reader = csv.DictReader(io.StringIO(text))
        return [dict(row) for row in reader]
