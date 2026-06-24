"""Generic HTML list-page scraper — last-resort tier (most fragile).

Config-driven CSS selectors so a new HTML source is a JSON edit. Use the
special selector value "self" when the matched item element IS the link
(e.g. item_selector picks <a> tags directly).

Config:
  collection_method: "html"   (or html_fallback block on an rss source)
  list_url, item_selector, title_selector, link_selector?, summary_selector?, base_url?
"""
from __future__ import annotations

from urllib.parse import urljoin

from bs4 import BeautifulSoup

from collectors.base import BaseCollector


def _pick(node, selector):
    return node if selector == "self" else node.select_one(selector)


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
        items, seen = [], set()
        for node in soup.select(item_sel):
            title_el = _pick(node, title_sel)
            link_el = _pick(node, link_sel)
            if not title_el:
                continue
            href = (link_el.get("href") if link_el else "") or ""
            if not href:
                continue
            url = urljoin(base_url, href)
            if url in seen:
                continue
            seen.add(url)
            summary = ""
            if summary_sel:
                sum_el = node.select_one(summary_sel)
                summary = sum_el.get_text(strip=True) if sum_el else ""
            items.append({
                "source": self.name,
                "title": title_el.get_text(strip=True),
                "url": url,
                "published_at": "",
                "content": "",
                "summary": summary,
                "tags": [],
                "author": "",
            })

        self.log.info("scraped %d items", len(items))
        return items
