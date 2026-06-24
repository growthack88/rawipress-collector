"""Collector registry: maps collection_method -> collector class."""
from collectors.rss import RSSCollector
from collectors.sitemap import SitemapCollector
from collectors.html import HTMLCollector

REGISTRY = {
    "rss": RSSCollector,
    "sitemap": SitemapCollector,
    "html": HTMLCollector,
}


def build_collector(source: dict):
    method = source.get("collection_method", "rss")
    cls = REGISTRY.get(method)
    if cls is None:
        raise ValueError(
            f"Unknown collection_method '{method}' for source '{source.get('name')}'. "
            f"Known: {', '.join(REGISTRY)}"
        )
    return cls(source)
