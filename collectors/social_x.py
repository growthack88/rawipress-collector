"""X / Twitter collector — the brittle, globally-reachable piece.

X is NOT the geo-blocked part, but it actively fights scraping, so the fetch
method is pluggable behind one function: `fetch_x_posts(handle, max_posts)`.
Method is chosen by what's configured in the environment, in order of
reliability:

  1. X API v2          (X_BEARER_TOKEN)   — most reliable, paid Basic tier
  2. Apify X scraper   (APIFY_TOKEN)      — robust, paid per run
  3. Nitter RSS        (NITTER_INSTANCES) — free, instances often down
  4. (none configured) → logs a clear error and returns []

Returns a list of raw_post dicts (the pipeline maps these to IngestItems):
  {url, text, posted_at, image, media_type, engagement{likes,retweets,replies,views}}
"""
from __future__ import annotations

import requests

from core import env
from utils.http import fetch
from utils.logger import get_logger
from utils.parser import to_iso

log = get_logger("collector.x")

_API_TIMEOUT = 30


def _tweet_url(handle: str, tweet_id: str) -> str:
    return f"https://x.com/{handle.lstrip('@')}/status/{tweet_id}"


# --------------------------------------------------------------------------- #
# Method 1: X API v2
# --------------------------------------------------------------------------- #
def _via_x_api(handle: str, max_posts: int, bearer: str) -> list[dict]:
    h = handle.lstrip("@")
    headers = {"Authorization": f"Bearer {bearer}"}
    # Resolve handle -> user id.
    u = requests.get(
        f"https://api.twitter.com/2/users/by/username/{h}",
        headers=headers, timeout=_API_TIMEOUT,
    )
    u.raise_for_status()
    user_id = u.json().get("data", {}).get("id")
    if not user_id:
        log.warning("[x] could not resolve user id for @%s", h)
        return []

    params = {
        "max_results": max(5, min(int(max_posts), 100)),
        "tweet.fields": "created_at,public_metrics,attachments,entities",
        "expansions": "attachments.media_keys",
        "media.fields": "url,preview_image_url,type",
        "exclude": "retweets,replies",
    }
    r = requests.get(
        f"https://api.twitter.com/2/users/{user_id}/tweets",
        headers=headers, params=params, timeout=_API_TIMEOUT,
    )
    r.raise_for_status()
    body = r.json()
    media = {m["media_key"]: m for m in body.get("includes", {}).get("media", [])}

    posts: list[dict] = []
    for tw in body.get("data", []):
        m = tw.get("public_metrics", {})
        image, media_type = "", ""
        keys = tw.get("attachments", {}).get("media_keys", [])
        if keys and keys[0] in media:
            md = media[keys[0]]
            media_type = "video" if md.get("type") in ("video", "animated_gif") else "image"
            image = md.get("url") or md.get("preview_image_url") or ""
        posts.append({
            "url": _tweet_url(h, tw["id"]),
            "text": tw.get("text", ""),
            "posted_at": to_iso(tw.get("created_at", "")),
            "image": image,
            "media_type": media_type,
            "engagement": {
                "likes": m.get("like_count", 0),
                "retweets": m.get("retweet_count", 0),
                "replies": m.get("reply_count", 0),
                "views": m.get("impression_count", 0),
            },
        })
    log.info("[x] @%s — %d posts via X API", h, len(posts))
    return posts


# --------------------------------------------------------------------------- #
# Method 2: Apify X scraper actor (run-sync-get-dataset-items)
# --------------------------------------------------------------------------- #
def _via_apify(handle: str, max_posts: int, token: str) -> list[dict]:
    h = handle.lstrip("@")
    actor = env.get("X_APIFY_ACTOR", "apidojo~tweet-scraper")
    url = f"https://api.apify.com/v2/acts/{actor}/run-sync-get-dataset-items?token={token}"
    payload = {
        "twitterHandles": [h],
        "maxItems": int(max_posts),
        "sort": "Latest",
    }
    r = requests.post(url, json=payload, timeout=180)
    r.raise_for_status()
    rows = r.json() if isinstance(r.json(), list) else []
    posts: list[dict] = []
    for it in rows[:max_posts]:
        tid = str(it.get("id") or it.get("id_str") or "")
        link = it.get("url") or it.get("twitterUrl") or (_tweet_url(h, tid) if tid else "")
        if not link:
            continue
        media_list = it.get("media") or it.get("extendedEntities", {}).get("media", []) or []
        image, media_type = "", ""
        if media_list:
            md = media_list[0]
            image = md.get("media_url_https") or md.get("url") or ""
            media_type = "video" if md.get("type") in ("video", "animated_gif") else "image"
        posts.append({
            "url": link,
            "text": it.get("text") or it.get("full_text") or "",
            "posted_at": to_iso(it.get("createdAt") or it.get("created_at") or ""),
            "image": image,
            "media_type": media_type,
            "engagement": {
                "likes": it.get("likeCount") or it.get("favorite_count") or 0,
                "retweets": it.get("retweetCount") or it.get("retweet_count") or 0,
                "replies": it.get("replyCount") or 0,
                "views": it.get("viewCount") or 0,
            },
        })
    log.info("[x] @%s — %d posts via Apify (%s)", h, len(posts), actor)
    return posts


# --------------------------------------------------------------------------- #
# Method 3: Nitter RSS (free, flaky)
# --------------------------------------------------------------------------- #
def _via_nitter(handle: str, max_posts: int, instances: list[str]) -> list[dict]:
    import feedparser
    from bs4 import BeautifulSoup

    h = handle.lstrip("@")
    for inst in instances:
        feed_url = f"{inst.rstrip('/')}/{h}/rss"
        try:
            resp = fetch(feed_url)
        except Exception as exc:
            log.warning("[x] nitter %s failed: %s", inst, exc)
            continue
        parsed = feedparser.parse(resp.content)
        if not parsed.entries:
            log.warning("[x] nitter %s returned no entries", inst)
            continue
        posts: list[dict] = []
        for entry in parsed.entries[:max_posts]:
            link = entry.get("link", "")
            # Nitter links point at the instance; rewrite to canonical x.com.
            tweet_id = link.rstrip("/").split("/")[-1].split("#")[0]
            canonical = _tweet_url(h, tweet_id) if tweet_id.isdigit() else link
            raw_html = entry.get("summary", "") or entry.get("description", "")
            soup = BeautifulSoup(raw_html, "lxml")
            img_el = soup.find("img")
            image = img_el.get("src", "") if img_el else ""
            text = soup.get_text(" ", strip=True)
            posts.append({
                "url": canonical,
                "text": text or entry.get("title", ""),
                "posted_at": to_iso(
                    getattr(entry, "published_parsed", None) or entry.get("published", "")
                ),
                "image": image,
                "media_type": "image" if image else "",
                "engagement": {},
            })
        log.info("[x] @%s — %d posts via Nitter (%s)", h, len(posts), inst)
        return posts
    log.error("[x] all Nitter instances failed for @%s", h)
    return []


# --------------------------------------------------------------------------- #
# Pluggable entry point
# --------------------------------------------------------------------------- #
def fetch_x_posts(handle: str, max_posts: int = 30) -> list[dict]:
    """Fetch recent posts for an X handle using the best configured method."""
    bearer = env.get("X_BEARER_TOKEN")
    if bearer:
        try:
            return _via_x_api(handle, max_posts, bearer)
        except Exception as exc:
            log.warning("[x] X API failed for @%s, trying fallbacks: %s", handle, exc)

    apify = env.get("APIFY_TOKEN")
    if apify:
        try:
            return _via_apify(handle, max_posts, apify)
        except Exception as exc:
            log.warning("[x] Apify failed for @%s, trying fallbacks: %s", handle, exc)

    instances_raw = env.get("NITTER_INSTANCES", "")
    instances = [s.strip() for s in instances_raw.split(",") if s.strip()]
    if instances:
        return _via_nitter(handle, max_posts, instances)

    log.error(
        "[x] no X fetch method configured for @%s — set X_BEARER_TOKEN, "
        "APIFY_TOKEN, or NITTER_INSTANCES in .env", handle,
    )
    return []
