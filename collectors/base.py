"""Base collector contract.

Every collector implements collect() and returns a list of RAW dicts:
[{"source","title","url","published_at","content","summary","tags"}, ...]

Normalization to the canonical model happens later (utils.parser.normalize),
so collectors stay simple and only worry about extraction.
"""
from __future__ import annotations

import requests

from utils.logger import get_logger

DEFAULT_HEADERS = {
    # Some Saudi gov/enterprise sites reject the default python-requests UA.
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36 "
        "RawiPress/1.0"
    ),
    "Accept-Language": "ar,en;q=0.8",
}


class BaseCollector:
    def __init__(self, source: dict, timeout: int = 20) -> None:
        self.source = source
        self.name = source.get("name", "unknown")
        self.timeout = timeout
        self.log = get_logger(f"collector.{self.name}")

    def fetch(self, url: str) -> requests.Response:
        resp = requests.get(
            url, headers=DEFAULT_HEADERS, timeout=self.timeout, allow_redirects=True
        )
        resp.raise_for_status()
        return resp

    def collect(self) -> list[dict]:  # pragma: no cover - interface
        raise NotImplementedError
