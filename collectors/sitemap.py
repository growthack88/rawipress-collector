"""Sitemap collector with full-article extraction (Phase 1 fix).

Before: stored bare URLs (empty title/content). Now: walks the sitemap,
filters to real article URLs, then fetches each and extracts title +
content + date + author via collectors.article.extract_article.

Config (sources.json):
  collection_method: "sitemap"
  sitemap_url: "<sitemap or sitemap-index url>"
  sitemap_url_contains: "/news"     # optional substring filter (recommended)
  sitemap_url_regex: "\\d{6,}"       # optional regex an article URL must match
  sitemap_max_urls: 30               # candidate URLs scanned per run
  extract_content: true              # default true; set false to store URLs only
"""
from __future__ import annotations

import re
from xml.etree import ElementTree as ET

from collectors.base import BaseCollector
from collectors.article import extract_article

_NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}


class SitemapCollector(BaseCollector):
    def _parse_sitemap(self, xml_bytes: bytes):
        root = ET.fromstring(xml_bytes)
        tag = root.tag.lower()
        if tag.endswith("sitemapindex"):
            return "index", [
                loc.text.strip()
                for loc in root.findall(".//sm:sitemap/sm:loc", _NS)
                if loc.text
            ]
        urls = []
        for url_el in root.findall(".//sm:url", _NS):
            loc = url_el.find("sm:loc", _NS)
            lastmod = url_el.find("sm:lastmod", _NS)
            if loc is not None and loc.text:
                urls.append({
                    "url": loc.text.strip(),
                    "lastmod": lastmod.text.strip() if lastmod is not None and lastmod.text else "",
                })
        return "urlset", urls

    def _gather_urls(self, sitemap_url: str, max_urls: int) -> list[dict]:
        try:
            resp = self.fetch(sitemap_url)
            kind, payload = self._parse_sitemap(resp.content)
        except Exception as exc:
            self.log.error("sitemap fetch/parse failed %s: %s", sitemap_url, exc)
            return []
        if kind == "urlset":
            return payload
        # index -> walk children until we have enough candidates. Walk NEWEST
        # first: date-partitioned indexes (e.g. /sitemaps/2017/1/...) list oldest
        # first, so reversed() gets the most recent months/sections.
        out: list[dict] = []
        for child in reversed(payload):
            if len(out) >= max_urls * 3:
                break
            try:
                cresp = self.fetch(child)
                ckind, curls = self._parse_sitemap(cresp.content)
                if ckind == "urlset":
                    out.extend(curls)
            except Exception as exc:
                self.log.warning("child sitemap failed %s: %s", child, exc)
        return out

    def collect(self) -> list[dict]:
        sitemap_url = self.source.get("sitemap_url")
        if not sitemap_url:
            self.log.error("no sitemap_url configured")
            return []

        max_urls = int(self.source.get("sitemap_max_urls", 30))
        contains = self.source.get("sitemap_url_contains", "")
        regex = self.source.get("sitemap_url_regex", "")
        pattern = re.compile(regex) if regex else None
        do_extract = self.source.get("extract_content", True)

        candidates = self._gather_urls(sitemap_url, max_urls)
        if contains:
            candidates = [u for u in candidates if contains in u["url"]]
        if pattern:
            candidates = [u for u in candidates if pattern.search(u["url"])]

        # Most-recently-modified first, then cap.
        candidates.sort(key=lambda u: u.get("lastmod", ""), reverse=True)
        candidates = candidates[:max_urls]

        items: list[dict] = []
        for u in candidates:
            base = {
                "source": self.name, "url": u["url"], "published_at": u.get("lastmod", ""),
                "title": "", "content": "", "summary": "", "tags": [], "author": "", "image": "",
            }
            if do_extract:
                try:
                    art = extract_article(u["url"])
                    base["title"] = art["title"]
                    base["content"] = art["content"]
                    base["author"] = art["author"]
                    base["image"] = art.get("image", "")
                    base["published_at"] = art["published_at"] or base["published_at"]
                except Exception as exc:
                    self.log.warning("extract failed %s: %s", u["url"], exc)
                    continue  # skip URL-only records; we want content
            items.append(base)

        self.log.info("collected %d articles from sitemap", len(items))
        return items
