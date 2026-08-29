from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

import requests


class FetchResult:
    def __init__(self, raw: bytes, content_hash: str):
        self.raw = raw
        self.content_hash = content_hash


class BaseConnector(ABC):
    """A connector knows how to fetch bytes from a location and parse them
    into a flat list of row-dicts that the pipeline can extract KPI values from."""

    source_type: str

    def fetch(self, location: str) -> FetchResult:
        raw = self._fetch_raw(location)
        return FetchResult(raw=raw, content_hash=hashlib.sha256(raw).hexdigest())

    def _fetch_raw(self, location: str) -> bytes:
        if location.startswith("http://") or location.startswith("https://"):
            resp = requests.get(location, timeout=30, headers={"User-Agent": "MinistryDashboardBot/1.0"})
            resp.raise_for_status()
            return resp.content
        return Path(location).read_bytes()

    @abstractmethod
    def parse(self, raw: bytes, config: dict[str, Any]) -> list[dict[str, Any]]:
        """Return a list of row-dicts extracted from the source."""
        ...
