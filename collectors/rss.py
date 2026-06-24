"""Generic RSS/Atom collector — covers the majority of media & some gov sources.

Config (sources.json):
  collection_method: "rss"
  rss_url: "<feed url>"
"""
from __future__ import annotations

import feedparser

from collectors.base import BaseCollector, DEFAULT_HEADERS


class RSSCollector(BaseCollector):
    def collect(self) -> list[dict]:
        feed_url = self.source.get("rss_url")
        if not feed_url:
            self.log.error("no rss_url configured")
            return []

        # Fetch via requests first (consistent UA/timeout, clearer errors),
        # then hand bytes to feedparser.
        try:
            resp = self.fetch(feed_url)
        except Exception as exc:
            self.log.error("fetch failed: %s", exc)
            return []

        parsed = feedparser.parse(resp.content)
        if parsed.bozo and not parsed.entries:
            self.log.error("feed parse error: %s", parsed.get("bozo_exception"))
            return []

        items: list[dict] = []
        for entry in parsed.entries:
            published = (
                getattr(entry, "published_parsed", None)
                or getattr(entry, "updated_parsed", None)
                or entry.get("published")
                or entry.get("updated")
                or ""
            )
            content = ""
            if entry.get("content"):
                content = entry["content"][0].get("value", "")
            content = content or entry.get("summary", "") or entry.get("description", "")

            tags = [t.get("term") for t in entry.get("tags", []) if t.get("term")]

            items.append(
                {
                    "source": self.name,
                    "title": entry.get("title", ""),
                    "url": entry.get("link", ""),
                    "published_at": published,
                    "content": content,
                    "summary": entry.get("summary", ""),
                    "tags": tags,
                }
            )

        self.log.info("parsed %d entries", len(items))
        return items
