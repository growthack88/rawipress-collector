"""Deduplication by URL hash and title hash.

A persistent seen-set lives in data/seen.json so dedup survives restarts
and stays O(1) per item without re-scanning the whole article store.
"""
import json
import os
import tempfile
from pathlib import Path

from utils.parser import url_id, title_hash

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SEEN_FILE = DATA_DIR / "seen.json"


class Deduplicator:
    def __init__(self) -> None:
        self._urls: set = set()
        self._titles: set = set()
        self._load()

    def _load(self) -> None:
        if SEEN_FILE.exists():
            try:
                with open(SEEN_FILE, encoding="utf-8") as fh:
                    data = json.load(fh)
                self._urls = set(data.get("urls", []))
                self._titles = set(data.get("titles", []))
            except (json.JSONDecodeError, OSError):
                pass

    def is_duplicate(self, item: dict) -> bool:
        if item.get("id") in self._urls:
            return True
        # Only treat title as a dedup key when it's non-empty — sitemap items
        # arrive title-less and must not all collapse onto the empty hash.
        title = item.get("title", "")
        return bool(title) and title_hash(title) in self._titles

    def add(self, item: dict) -> None:
        self._urls.add(item.get("id") or url_id(item.get("url", "")))
        title = item.get("title", "")
        if title:
            self._titles.add(title_hash(title))

    def filter_new(self, items: list) -> list:
        """Return only items not seen before; records them as seen."""
        fresh = []
        for item in items:
            if self.is_duplicate(item):
                continue
            self.add(item)
            fresh.append(item)
        return fresh

    def save(self) -> None:
        SEEN_FILE.parent.mkdir(parents=True, exist_ok=True)
        payload = {"urls": sorted(self._urls), "titles": sorted(self._titles)}
        fd, tmp = tempfile.mkstemp(dir=str(SEEN_FILE.parent), suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, ensure_ascii=False)
            os.replace(tmp, SEEN_FILE)
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)
