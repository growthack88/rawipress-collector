"""Base collector contract.

Every collector implements collect() and returns a list of RAW dicts:
[{"source","title","url","published_at","content","summary","tags","author","image"}, ...]

Normalization (utils.parser.normalize) and mapping to IngestItems happen
downstream in core.pipeline, so collectors only do extraction. The cloud
ingest pipeline does dedup/summary/entities — never here.
"""
from __future__ import annotations

from utils.http import fetch
from utils.logger import get_logger


class BaseCollector:
    def __init__(self, source: dict, timeout: int = 25) -> None:
        self.source = source
        self.name = source.get("name", "unknown")
        self.timeout = timeout
        self.log = get_logger(f"collector.{self.name}")

    def fetch(self, url: str):
        return fetch(url, timeout=self.timeout)

    def collect(self) -> list[dict]:  # pragma: no cover - interface
        raise NotImplementedError
