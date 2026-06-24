"""Generic HTML list-page scraper — for sources with neither RSS nor sitemap.

Config-driven CSS selectors so a new HTML source is a JSON edit, not new code.
HTML scraping is the most fragile method (markup changes break it), so it's
the last-resort tier per the collection strategy.

Config (sources.json):
  collection_method: "html"
  list_url:        "<page listing articles>"
  item_selector:   "article.card"        # each article container
  title_selector:  "h2 a"                 # within item; text + href
  link_selector:   "h2 a"                 # within item; href (defaults to title_selector)
  summary_selector:".excerpt"             # optional
  base_url:        "https://example.com"  # to resolve relative links (defaults to source_url)
"""
from __future__ import annotations

from urllib.parse import urljoin

from bs4 import BeautifulSoup

from collectors.base import BaseCollector


class HTMLCollector(BaseCollector):
    def collect(self) -> list[dict]:
        list_url = self.source.get("list_url") or self.source.get("source_url")
        item_sel = self.source.get("item_selector")
        title_sel = self.source.get("title_selector")
        if not (list_url and item_sel and title_sel):
            self.log.error("html collector needs list_url, item_selector, title_selector")
            return []

        link_sel = self.source.get("link_selector", title_sel)
        summary_sel = self.source.get("summary_selector")
        base_url = self.source.get("base_url") or self.source.get("source_url") or list_url

        try:
            resp = self.fetch(list_url)
        except Exception as exc:
            self.log.error("fetch failed: %s", exc)
            return []

        soup = BeautifulSoup(resp.text, "lxml")
        items: list[dict] = []
        for node in soup.select(item_sel):
            title_el = node.select_one(title_sel)
            link_el = node.select_one(link_sel)
            if not title_el:
                continue
            href = (link_el.get("href") if link_el else "") or ""
            summary = ""
            if summary_sel:
                sum_el = node.select_one(summary_sel)
                summary = sum_el.get_text(strip=True) if sum_el else ""
            items.append(
                {
                    "source": self.name,
                    "title": title_el.get_text(strip=True),
                    "url": urljoin(base_url, href),
                    "published_at": "",
                    "content": "",
                    "summary": summary,
                    "tags": [],
                }
            )

        self.log.info("scraped %d items", len(items))
        return items
