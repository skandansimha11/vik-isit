from __future__ import annotations

import io
from typing import Any

import pdfplumber

from app.connectors.base import BaseConnector


class PDFConnector(BaseConnector):
    source_type = "pdf"

    def parse(self, raw: bytes, config: dict[str, Any]) -> list[dict[str, Any]]:
        page_num = config.get("page", 0)
        table_index = config.get("table_index", 0)

        with pdfplumber.open(io.BytesIO(raw)) as pdf:
            if page_num >= len(pdf.pages):
                return []
            page = pdf.pages[page_num]
            tables = page.extract_tables()

        if not tables or table_index >= len(tables):
            return []

        table = tables[table_index]
        if not table:
            return []

        header = [str(h).strip() if h is not None else "" for h in table[0]]
        records = []
        for row in table[1:]:
            records.append({header[i]: row[i] for i in range(len(header)) if i < len(row)})
        return records
