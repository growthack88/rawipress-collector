"""Robust RSS/Atom collector.

Strategy (Phase 1 hardening):
  1. feedparser on the fetched bytes (handles most feeds).
  2. If that yields nothing, retry feedparser on a lenient lxml/BeautifulSoup
     re-serialization — recovers feeds with stray/invalid tokens (Argaam, Sabq).
  3. If still nothing and html_fallback is configured, defer to HTMLCollector.

Config (sources.json):
  collection_method: "rss"
  rss_url: "<feed url>"
  rss_fallbacks: ["<alt feed url>", ...]   # optional
  html_fallback: { ...HTMLCollector config... }  # optional last resort
"""
from __future__ import annotations

import feedparser
from bs4 import BeautifulSoup

from collectors.base import BaseCollector


class RSSCollector(BaseCollector):
    def _parse(self, raw_bytes: bytes):
        parsed = feedparser.parse(raw_bytes)
        if parsed.entries:
            return parsed
        # Lenient recovery: re-serialize via BeautifulSoup's xml parser, which
        # tolerates malformed markup, then hand clean XML back to feedparser.
        try:
            soup = BeautifulSoup(raw_bytes, "xml")
            cleaned = str(soup).encode("utf-8")
            parsed2 = feedparser.parse(cleaned)
            if parsed2.entries:
                self.log.info("recovered feed via lenient xml reparse")
                return parsed2
        except Exception as exc:
            self.log.warning("lenient reparse failed: %s", exc)
        return parsed

    def _entries_to_items(self, parsed) -> list[dict]:
        items = []
        for entry in parsed.entries:
            published = (
                getattr(entry, "published_parsed", None)
                or getattr(entry, "updated_parsed", None)
                or entry.get("published") or entry.get("updated") or ""
            )
            content = ""
            if entry.get("content"):
                content = entry["content"][0].get("value", "")
            content = content or entry.get("summary", "") or entry.get("description", "")
            tags = [t.get("term") for t in entry.get("tags", []) if t.get("term")]
            items.append({
                "source": self.name,
                "title": entry.get("title", ""),
                "url": entry.get("link", ""),
                "published_at": published,
                "content": content,
                "summary": entry.get("summary", ""),
                "tags": tags,
                "author": entry.get("author", ""),
            })
        return items

    def collect(self) -> list[dict]:
        urls = [self.source.get("rss_url")] + list(self.source.get("rss_fallbacks", []))
        urls = [u for u in urls if u]
        if not urls:
            self.log.error("no rss_url configured")
            return []

        for feed_url in urls:
            try:
                resp = self.fetch(feed_url)
            except Exception as exc:
                self.log.warning("fetch failed %s: %s", feed_url, exc)
                continue
            parsed = self._parse(resp.content)
            if parsed.entries:
                items = self._entries_to_items(parsed)
                self.log.info("parsed %d entries from %s", len(items), feed_url)
                return items
            self.log.warning("no entries from %s (bozo=%s)", feed_url, parsed.get("bozo"))

        # Last resort: HTML scrape of a listing page.
        html_cfg = self.source.get("html_fallback")
        if html_cfg:
            from collectors.html import HTMLCollector
            self.log.info("falling back to HTML collector")
            merged = {**self.source, **html_cfg}
            return HTMLCollector(merged).collect()

        self.log.error("all RSS sources failed for %s", self.name)
        return []
