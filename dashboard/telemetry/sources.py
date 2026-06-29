"""Read and model the source registry (``config/sources.json``).

The registry is the node's plan of record: every news source and social
channel it is configured to collect, whether each is enabled, whether its feed
path has been verified inside KSA, and whether it is wired to a cloud channel.
"""
from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from dashboard.telemetry.paths import SOURCES_FILE

# channel_id values that mean "not wired to the cloud yet" (mirrors pipeline).
_PLACEHOLDERS = {"", "PASTE-UUID-HERE", "PASTE-CHANNEL-UUID", "PASTE-CHANNEL-UUID-HERE"}


@dataclass(frozen=True)
class Source:
    """One configured collection target (news source or social channel)."""

    name: str
    display_name: str
    category: str
    kind: str  # "news" | "social"
    method: str  # rss | sitemap | html | x ...
    enabled: bool
    verified: bool
    wired: bool  # has a real channel_id
    priority: int
    target: str  # source_url or @handle

    @property
    def status(self) -> str:
        """Coarse health bucket used for colouring: online | warning | offline."""
        if not self.enabled:
            return "offline"
        if not self.verified or not self.wired:
            return "warning"
        return "online"


def _coerce(entry: dict, kind: str) -> Source:
    cid = (str(entry.get("channel_id") or "")).strip()
    if kind == "social":
        method = entry.get("platform", "x")
        target = "@" + str(entry.get("handle", "")).lstrip("@")
    else:
        method = entry.get("collection_method", "?")
        target = entry.get("source_url", "")
    return Source(
        name=entry.get("name", "?"),
        display_name=entry.get("display_name") or entry.get("name", "?"),
        category=entry.get("category", "uncategorized"),
        kind=kind,
        method=method,
        enabled=bool(entry.get("enabled", True)),
        verified=bool(entry.get("verified", False)),
        wired=cid not in _PLACEHOLDERS,
        priority=int(entry.get("priority", 9)),
        target=target,
    )


def load_sources(path: Path = SOURCES_FILE) -> list[Source]:
    """Parse the registry. Returns ``[]`` (not an error) if the file is absent."""
    if not path.exists():
        return []
    try:
        cfg = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    news = cfg.get("news") or cfg.get("sources") or []
    social = cfg.get("social") or []
    out = [_coerce(e, "news") for e in news]
    out += [_coerce(e, "social") for e in social]
    return out


@dataclass(frozen=True)
class RegistrySummary:
    total: int
    enabled: int
    verified: int
    wired: int
    news: int
    social: int
    by_category: dict[str, int]
    by_method: dict[str, int]


def summarize(sources: list[Source]) -> RegistrySummary:
    cats: Counter[str] = Counter(s.category for s in sources)
    methods: Counter[str] = Counter(s.method for s in sources)
    return RegistrySummary(
        total=len(sources),
        enabled=sum(1 for s in sources if s.enabled),
        verified=sum(1 for s in sources if s.verified),
        wired=sum(1 for s in sources if s.wired),
        news=sum(1 for s in sources if s.kind == "news"),
        social=sum(1 for s in sources if s.kind == "social"),
        by_category=dict(cats.most_common()),
        by_method=dict(methods.most_common()),
    )


__all__ = ["Source", "RegistrySummary", "load_sources", "summarize"]
