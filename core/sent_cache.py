"""Optional local cache of already-sent original_urls.

Pure bandwidth optimization — correctness does NOT depend on it because the
cloud dedups every item before any AI call. OFF by default so the default run
always POSTs and the cloud's {found,new,skipped} response stays the source of
truth (and the dedup acceptance test is meaningful). Enable with:

    RAWI_SENT_CACHE=1

State is a JSON object {url: epoch_seconds} under data/ (gitignored), pruned
to the newest MAX_ENTRIES so it can't grow without bound.
"""
from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path

from core import env
from utils.logger import get_logger

log = get_logger("sent_cache")

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CACHE_FILE = DATA_DIR / "sent_urls.json"
MAX_ENTRIES = 50_000


def enabled() -> bool:
    return (env.get("RAWI_SENT_CACHE", "0") or "0").lower() in ("1", "true", "yes", "on")


class SentCache:
    def __init__(self) -> None:
        self._seen: dict[str, float] = {}
        self._dirty = False
        if enabled():
            self._load()

    def _load(self) -> None:
        if CACHE_FILE.exists():
            try:
                with open(CACHE_FILE, encoding="utf-8") as fh:
                    self._seen = json.load(fh)
            except (json.JSONDecodeError, OSError) as exc:
                log.warning("could not read sent cache, starting fresh: %s", exc)
                self._seen = {}

    def is_sent(self, url: str) -> bool:
        return bool(url) and url in self._seen

    def mark(self, url: str) -> None:
        if url:
            self._seen[url] = time.time()
            self._dirty = True

    def filter_unsent(self, items: list[dict]) -> list[dict]:
        """Drop items whose original_url we've already POSTed (when enabled)."""
        if not enabled():
            return items
        return [it for it in items if not self.is_sent(it.get("original_url", ""))]

    def save(self) -> None:
        if not (enabled() and self._dirty):
            return
        # Prune oldest entries past the cap.
        if len(self._seen) > MAX_ENTRIES:
            newest = sorted(self._seen.items(), key=lambda kv: kv[1], reverse=True)[:MAX_ENTRIES]
            self._seen = dict(newest)
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=str(CACHE_FILE.parent), suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(self._seen, fh, ensure_ascii=False)
            os.replace(tmp, CACHE_FILE)
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)
