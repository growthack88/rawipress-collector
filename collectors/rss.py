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
            image = ""
            if entry.get("media_content"):
                image = entry["media_content"][0].get("url", "")
            if not image and entry.get("media_thumbnail"):
                image = entry["media_thumbnail"][0].get("url", "")
            if not image:
                for enc in entry.get("links", []):
                    if enc.get("rel") == "enclosure" and "image" in (enc.get("type") or ""):
                        image = enc.get("href", "")
                        break
            items.append({
                "source": self.name,
                "title": entry.get("title", ""),
                "url": entry.get("link", ""),
                "published_at": published,
                "content": content,
                "summary": entry.get("summary", ""),
                "tags": tags,
                "author": entry.get("author", ""),
                "image": image,
            })
        return items

    def _fetch_full_bodies(self, items: list[dict]) -> list[dict]:
        """Follow each entry's link and replace the snippet with the full article
        body (RSS often gives only a summary; AI summary quality wants full text).
        Bounded by full_content_max; falls back to the RSS snippet on failure."""
        from collectors.article import extract_article

        limit = int(self.source.get("full_content_max", 25))
        enriched = 0
        for item in items[:limit]:
            url = item.get("url")
            if not url:
                continue
            try:
                art = extract_article(url)
            except Exception as exc:
                self.log.warning("full-content fetch failed %s: %s", url, exc)
                continue
            if art.get("content") and len(art["content"]) > len(item.get("content", "")):
                item["content"] = art["content"]
                enriched += 1
            item["image"] = item.get("image") or art.get("image", "")
            if art.get("published_at"):
                item["published_at"] = item.get("published_at") or art["published_at"]
            if art.get("author"):
                item["author"] = item.get("author") or art["author"]
        self.log.info("full-content: enriched %d/%d entries", enriched, min(len(items), limit))
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
                if self.source.get("fetch_full_content"):
                    items = self._fetch_full_bodies(items)
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
