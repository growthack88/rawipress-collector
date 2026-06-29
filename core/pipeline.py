"""Push-only collection pipeline.

collect (reuse existing collectors) -> map to IngestItem -> POST to the cloud
`ingest` edge function. The cloud does dedup, AI summary, entities, story
grouping, and storage; the collector stores and computes nothing.

Per-source failures are isolated: one bad feed/handle logs an error and the
rest of the run still completes.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from collectors import build_collector
from collectors.social_x import fetch_x_posts
from core import ingest_client
from core.sent_cache import SentCache
from utils.logger import get_logger
from utils.parser import canonical_url, normalize, to_iso

ROOT = Path(__file__).resolve().parent.parent
SOURCES_FILE = ROOT / "config" / "sources.json"
log = get_logger("pipeline")

# channel_id values that mean "not wired up yet" — such sources are skipped.
_PLACEHOLDERS = {"", "PASTE-UUID-HERE", "PASTE-CHANNEL-UUID", "PASTE-CHANNEL-UUID-HERE"}


def _config() -> dict:
    with open(SOURCES_FILE, encoding="utf-8") as fh:
        return json.load(fh)


def load_sources() -> list[dict]:
    """News sources. Accepts the new 'news' key, falls back to legacy 'sources'."""
    cfg = _config()
    return cfg.get("news") or cfg.get("sources", [])


def load_social() -> list[dict]:
    return _config().get("social", [])


def _has_channel(entry: dict) -> bool:
    cid = (entry.get("channel_id") or "").strip()
    if cid in _PLACEHOLDERS:
        log.warning("[%s] no channel_id set — skipping (create the channel "
                    "in source_channels, then paste its id into sources.json)",
                    entry.get("name", "?"))
        return False
    return True


# --------------------------------------------------------------------------- #
# Mapping: raw collector output -> IngestItem
# --------------------------------------------------------------------------- #
def _drop_empty(item: dict) -> dict:
    """Keep required + non-empty optional fields (original_url always kept)."""
    return {k: v for k, v in item.items() if k == "original_url" or v not in ("", None, {})}


def news_to_ingest(raw_items: list[dict], source: dict) -> list[dict]:
    items: list[dict] = []
    for raw in raw_items:
        if not raw.get("url"):
            continue
        n = normalize(raw, source)
        body = n["content"] or n["summary"]
        items.append(_drop_empty({
            "original_url": n["url"],
            "title": n["title"],
            "body": body,
            "media_url": n["image"],
            "media_type": "image" if n["image"] else "",
            "posted_at": n["published_at"],
        }))
    return items


def social_to_ingest(posts: list[dict]) -> list[dict]:
    items: list[dict] = []
    for p in posts:
        url = canonical_url(p.get("url", ""))
        if not url:
            continue
        text = (p.get("text") or "").strip()
        items.append(_drop_empty({
            "original_url": url,
            "title": text[:80],
            "body": text,
            "media_url": p.get("image", ""),
            "media_type": p.get("media_type", ""),
            "posted_at": to_iso(p.get("posted_at", "")),
            "raw_engagement": p.get("engagement") or {},
        }))
    return items


# --------------------------------------------------------------------------- #
# Per-source / per-channel runs
# --------------------------------------------------------------------------- #
def run_news_source(source: dict, cache: SentCache, dry_run: bool = False) -> dict:
    name = source.get("name", "?")
    if not source.get("enabled", True):
        return {"source": name, "skipped": "disabled"}
    if not dry_run and not _has_channel(source):
        return {"source": name, "skipped": "no_channel"}
    try:
        raw = build_collector(source).collect()
        items = news_to_ingest(raw, source)
        return _send(name, source.get("channel_id", ""), items, cache, dry_run)
    except Exception as exc:
        log.exception("[%s] news collection failed", name)
        return {"source": name, "status": "error", "error": f"{type(exc).__name__}: {exc}"}


def run_social_channel(chan: dict, cache: SentCache, dry_run: bool = False) -> dict:
    name = chan.get("name", "?")
    if not chan.get("enabled", True):
        return {"source": name, "skipped": "disabled"}
    if not dry_run and not _has_channel(chan):
        return {"source": name, "skipped": "no_channel"}
    platform = chan.get("platform", "x")
    if platform != "x":
        log.warning("[%s] unsupported social platform '%s' — skipping", name, platform)
        return {"source": name, "skipped": f"unsupported:{platform}"}
    try:
        posts = fetch_x_posts(chan["handle"], int(chan.get("max_posts", 30)))
        items = social_to_ingest(posts)
        return _send(name, chan.get("channel_id", ""), items, cache, dry_run)
    except Exception as exc:
        log.exception("[%s] social collection failed", name)
        return {"source": name, "status": "error", "error": f"{type(exc).__name__}: {exc}"}


def _send(name: str, channel_id: str, items: list[dict], cache: SentCache, dry_run: bool) -> dict:
    mapped = len(items)
    items = cache.filter_unsent(items)
    if dry_run:
        log.info("[%s] DRY-RUN — %d items mapped (%d after local cache)", name, mapped, len(items))
        return {"source": name, "status": "dry-run", "mapped": mapped, "items": items}
    if not items:
        log.info("[%s] nothing to send (%d mapped, all cached)", name, mapped)
        return {"source": name, "status": "ok", "mapped": mapped,
                "found": 0, "new": 0, "skipped": 0}
    result = ingest_client.post_items(channel_id, items)
    for it in items:
        cache.mark(it["original_url"])
    log.info("[%s] ok — %d sent, found=%s new=%s skipped=%s",
             name, len(items), result.get("found"), result.get("new"), result.get("skipped"))
    return {"source": name, "status": "ok", "mapped": mapped, **result}


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #
def run_collection(source_names: list[str] | None = None,
                   include_social: bool = True,
                   dry_run: bool = False) -> dict:
    news = load_sources()
    social = load_social() if include_social else []
    if source_names:
        wanted = set(source_names)
        news = [s for s in news if s.get("name") in wanted]
        social = [s for s in social if s.get("name") in wanted]

    run_id = datetime.now(timezone.utc).strftime("run-%Y%m%dT%H%M%SZ")
    log.info("=== %s: %d news + %d social%s ===",
             run_id, len(news), len(social), " (dry-run)" if dry_run else "")

    cache = SentCache()
    results: list[dict] = []
    for s in news:
        results.append(run_news_source(s, cache, dry_run))
    for c in social:
        results.append(run_social_channel(c, cache, dry_run))
    cache.save()

    total_new = sum(r.get("new", 0) for r in results)
    total_sent = sum(len(r.get("items", [])) if dry_run else r.get("mapped", 0) for r in results)
    log.info("=== run complete: %d items, %d new ===", total_sent, total_new)
    return {"run_id": run_id, "total_new": total_new, "results": results}
