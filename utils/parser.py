"""Normalization helpers: turn raw collector output into the canonical
Rawi Press data model.

Canonical item:
{
  "id":           str,   # stable sha1 of the canonical url (primary key)
  "source":       str,   # source name, e.g. "arabnews"
  "category":     str,   # e.g. "media" | "government" | "financial"
  "title":        str,
  "url":          str,   # canonical (tracking params stripped)
  "published_at": str,   # ISO-8601 UTC, or "" if unknown
  "content":      str,
  "summary":      str,
  "tags":         list,
  "collected_at": str    # ISO-8601 UTC
}
"""
import hashlib
import re
from datetime import datetime, timezone
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

# Tracking params we strip so the same article from different referrers dedupes.
_TRACKING_PREFIXES = ("utm_", "fbclid", "gclid", "mc_", "ref", "spm")

_WS_RE = re.compile(r"\s+")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonical_url(url: str) -> str:
    """Lowercase host, drop fragment, strip tracking query params, trim trailing slash."""
    if not url:
        return ""
    url = url.strip()
    parts = urlsplit(url)
    query = [
        (k, v)
        for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if not any(k.lower().startswith(p) for p in _TRACKING_PREFIXES)
    ]
    path = parts.path.rstrip("/") or "/"
    return urlunsplit(
        (parts.scheme, parts.netloc.lower(), path, urlencode(query), "")
    )


def clean_text(value: str) -> str:
    if not value:
        return ""
    # strip tags if any slipped through, collapse whitespace
    value = re.sub(r"<[^>]+>", " ", value)
    return _WS_RE.sub(" ", value).strip()


def to_iso(value) -> str:
    """Accept datetime, time.struct_time, or string; return ISO-8601 UTC or ''."""
    if not value:
        return ""
    if isinstance(value, datetime):
        dt = value
    else:
        # feedparser exposes time.struct_time (e.g. entry.published_parsed)
        try:
            import time

            if hasattr(value, "tm_year"):
                dt = datetime.fromtimestamp(time.mktime(value), tz=timezone.utc)
            else:
                return str(value).strip()
        except Exception:
            return str(value).strip()
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()


def url_id(url: str) -> str:
    return hashlib.sha1(canonical_url(url).encode("utf-8")).hexdigest()


def title_hash(title: str) -> str:
    return hashlib.sha1(clean_text(title).lower().encode("utf-8")).hexdigest()


def normalize(raw: dict, source: dict) -> dict:
    """Map a collector's raw dict onto the canonical model.

    `source` is the matching entry from sources.json (for name/category).
    """
    url = canonical_url(raw.get("url", ""))
    return {
        "id": url_id(url),
        "source": source.get("name", raw.get("source", "")),
        "category": source.get("category", raw.get("category", "")),
        "title": clean_text(raw.get("title", "")),
        "url": url,
        "published_at": to_iso(raw.get("published_at", "")),
        "content": clean_text(raw.get("content", "")),
        "summary": clean_text(raw.get("summary", "")),
        "tags": raw.get("tags", []) or [],
        "author": clean_text(raw.get("author", "")),
        "collected_at": now_iso(),
    }
