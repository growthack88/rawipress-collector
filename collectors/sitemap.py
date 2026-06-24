"""Generic sitemap collector — for sources that publish a sitemap.xml but
no usable RSS (common for Saudi gov portals like SPA).

Walks the sitemap (following <sitemapindex> one level into child sitemaps),
emits URL entries with <lastmod> as published_at. Title/content are left
empty here; a Phase-2 enrichment step can fetch each URL for full text.

Config (sources.json):
  collection_method: "sitemap"
  sitemap_url: "<sitemap url>"
  sitemap_max_urls: 200          # optional cap per run (default 200)
  sitemap_url_contains: "/news"  # optional substring filter
"""
from __future__ import annotations

from xml.etree import ElementTree as ET

from collectors.base import BaseCollector

_NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}


class SitemapCollector(BaseCollector):
    def _parse_sitemap(self, xml_bytes: bytes):
        root = ET.fromstring(xml_bytes)
        tag = root.tag.lower()
        # Either a <sitemapindex> (links to more sitemaps) or a <urlset>.
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
                urls.append(
                    {"url": loc.text.strip(), "lastmod": lastmod.text.strip() if lastmod is not None and lastmod.text else ""}
                )
        return "urlset", urls

    def collect(self) -> list[dict]:
        sitemap_url = self.source.get("sitemap_url")
        if not sitemap_url:
            self.log.error("no sitemap_url configured")
            return []

        max_urls = int(self.source.get("sitemap_max_urls", 200))
        contains = self.source.get("sitemap_url_contains", "")

        try:
            resp = self.fetch(sitemap_url)
            kind, payload = self._parse_sitemap(resp.content)
        except Exception as exc:
            self.log.error("sitemap fetch/parse failed: %s", exc)
            return []

        url_entries: list[dict] = []
        if kind == "index":
            # Follow child sitemaps until we hit the cap.
            for child in payload:
                if len(url_entries) >= max_urls:
                    break
                try:
                    child_resp = self.fetch(child)
                    ckind, curls = self._parse_sitemap(child_resp.content)
                    if ckind == "urlset":
                        url_entries.extend(curls)
                except Exception as exc:
                    self.log.warning("child sitemap failed %s: %s", child, exc)
        else:
            url_entries = payload

        if contains:
            url_entries = [u for u in url_entries if contains in u["url"]]
        url_entries = url_entries[:max_urls]

        items = [
            {
                "source": self.name,
                "title": "",  # enriched in a later phase
                "url": u["url"],
                "published_at": u.get("lastmod", ""),
                "content": "",
                "summary": "",
                "tags": [],
            }
            for u in url_entries
        ]
        self.log.info("collected %d sitemap urls", len(items))
        return items
