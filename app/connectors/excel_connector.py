from __future__ import annotations

import io
from typing import Any

import openpyxl

from app.connectors.base import BaseConnector


class ExcelConnector(BaseConnector):
    source_type = "excel"

    def parse(self, raw: bytes, config: dict[str, Any]) -> list[dict[str, Any]]:
        wb = openpyxl.load_workbook(io.BytesIO(raw), data_only=True)
        sheet_name = config.get("sheet_name")
        ws = wb[sheet_name] if sheet_name else wb.active

        rows = list(ws.iter_rows(values_only=True))
        if not rows:
            return []

        header = [str(h).strip() if h is not None else "" for h in rows[0]]
        records = []
        for row in rows[1:]:
            if all(cell is None for cell in row):
                continue
            records.append({header[i]: row[i] for i in range(len(header)) if i < len(row)})
        return records
