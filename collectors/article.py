"""Article content extractor — fetch a URL and pull structured fields.

Used by the sitemap collector (SPA etc.) and as a fallback enricher for
feeds that only give a link. Dependency-light readability heuristic:
prefer JSON-LD / OpenGraph / <meta>, then fall back to the densest block
of <p> text. Works for both Arabic and English pages.
"""
from __future__ import annotations

import json
import re

from bs4 import BeautifulSoup

from utils.http import fetch
from utils.logger import get_logger

log = get_logger("collector.article")

_DATE_META = [
    ("meta", {"property": "article:published_time"}),
    ("meta", {"name": "article:published_time"}),
    ("meta", {"property": "og:updated_time"}),
    ("meta", {"name": "publishdate"}),
    ("meta", {"name": "date"}),
    ("meta", {"itemprop": "datePublished"}),
]
_AUTHOR_META = [
    ("meta", {"name": "author"}),
    ("meta", {"property": "article:author"}),
    ("meta", {"itemprop": "author"}),
]


def _meta(soup: BeautifulSoup, candidates) -> str:
    for tag, attrs in candidates:
        el = soup.find(tag, attrs=attrs)
        if el and el.get("content"):
            return el["content"].strip()
    return ""


def _json_ld(soup: BeautifulSoup) -> dict:
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "{}")
        except (json.JSONDecodeError, TypeError):
            continue
        items = data if isinstance(data, list) else [data]
        for it in items:
            if isinstance(it, dict) and it.get("@type") in (
                "NewsArticle", "Article", "ReportageNewsArticle", "BlogPosting"
            ):
                return it
    return {}


def _extract_content(soup: BeautifulSoup) -> str:
    # Drop noise.
    for sel in ("script", "style", "nav", "header", "footer", "aside", "form", "figure"):
        for el in soup.select(sel):
            el.decompose()
    # Prefer a semantic container; else the whole document.
    container = soup.find("article") or soup.find("main") or soup
    paragraphs = [p.get_text(" ", strip=True) for p in container.find_all("p")]
    paragraphs = [p for p in paragraphs if len(p) > 40]
    text = "\n".join(paragraphs)
    return re.sub(r"\s+\n", "\n", text).strip()


def extract_article(url: str) -> dict:
    """Return {title, content, published_at, author} for an article URL.

    Raises on fetch error so the caller can log + skip.
    """
    resp = fetch(url)
    soup = BeautifulSoup(resp.text, "lxml")
    ld = _json_ld(soup)

    title = (
        ld.get("headline")
        or _meta(soup, [("meta", {"property": "og:title"})])
        or (soup.title.string.strip() if soup.title and soup.title.string else "")
    )
    if not title:
        h1 = soup.find("h1")
        title = h1.get_text(strip=True) if h1 else ""

    content = ""
    body = ld.get("articleBody")
    if isinstance(body, str) and len(body) > 80:
        content = body.strip()
    if not content:
        content = _extract_content(soup)
    if not content:
        content = _meta(soup, [("meta", {"property": "og:description"}), ("meta", {"name": "description"})])

    published = (
        (ld.get("datePublished") if isinstance(ld.get("datePublished"), str) else "")
        or _meta(soup, _DATE_META)
    )
    author = _AUTHOR_META and _meta(soup, _AUTHOR_META) or ""
    if not author and isinstance(ld.get("author"), dict):
        author = ld["author"].get("name", "")

    image = _meta(soup, [("meta", {"property": "og:image"}), ("meta", {"name": "twitter:image"})])
    if not image:
        ld_img = ld.get("image")
        if isinstance(ld_img, str):
            image = ld_img
        elif isinstance(ld_img, dict):
            image = ld_img.get("url", "")
        elif isinstance(ld_img, list) and ld_img:
            first = ld_img[0]
            image = first.get("url", "") if isinstance(first, dict) else str(first)

    return {
        "title": title,
        "content": content,
        "published_at": published,
        "author": author,
        "image": image,
    }
