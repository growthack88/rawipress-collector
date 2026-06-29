"""HTTP client for the cloud `ingest` edge function.

Replaces the old SQLite layer (core/db.py). The collector is push-only: it
POSTs batches of raw items and the cloud does dedup → AI summary → entities →
story → store. This module knows nothing about article shape beyond the
IngestItem contract.

Endpoint:   POST {SUPABASE_URL}/functions/v1/ingest
Headers:    X-Ingest-Secret, Authorization: Bearer {service role key}
Body:       {"channel_id": "<uuid>", "items": [IngestItem, ...]}
Response:   {"found": N, "new": M, "skipped": K}
"""
from __future__ import annotations

import time

import requests

from core import env
from utils.logger import get_logger

log = get_logger("ingest")

MAX_BATCH = 25          # items per POST (contract: <= 25)
_TIMEOUT = 45
_MAX_RETRIES = 3        # on 5xx / network errors
_BACKOFF = 2.0          # seconds, multiplied each retry


class IngestError(RuntimeError):
    """Raised when a batch ultimately fails to POST (after retries)."""


def _endpoint() -> str:
    base = env.get("SUPABASE_URL", required=True).rstrip("/")
    return f"{base}/functions/v1/ingest"


def _headers() -> dict:
    return {
        "Content-Type": "application/json",
        "X-Ingest-Secret": env.get("INGEST_SECRET", required=True),
        "Authorization": f"Bearer {env.get('SUPABASE_SERVICE_ROLE_KEY', required=True)}",
    }


def _post_batch(endpoint: str, headers: dict, channel_id: str, items: list[dict]) -> dict:
    payload = {"channel_id": channel_id, "items": items}
    last_exc: Exception | None = None
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            resp = requests.post(endpoint, json=payload, headers=headers, timeout=_TIMEOUT)
        except requests.RequestException as exc:
            last_exc = exc
            log.warning("ingest network error (attempt %d/%d): %s", attempt, _MAX_RETRIES, exc)
        else:
            if resp.status_code < 400:
                try:
                    return resp.json()
                except ValueError:
                    return {"found": len(items), "new": 0, "skipped": 0, "raw": resp.text}
            # 4xx is a contract error — retrying won't help. Fail loudly.
            if resp.status_code < 500:
                raise IngestError(
                    f"ingest rejected batch: HTTP {resp.status_code} {resp.text[:300]}"
                )
            last_exc = IngestError(f"HTTP {resp.status_code}: {resp.text[:200]}")
            log.warning("ingest 5xx (attempt %d/%d): %s", attempt, _MAX_RETRIES, last_exc)
        if attempt < _MAX_RETRIES:
            time.sleep(_BACKOFF * attempt)
    raise IngestError(f"ingest failed after {_MAX_RETRIES} attempts: {last_exc}")


def post_items(channel_id: str, items: list[dict]) -> dict:
    """POST items for one channel, auto-chunked into batches of <= MAX_BATCH.

    Returns aggregated {found, new, skipped} across all batches.
    Raises IngestError if any batch fails after retries.
    """
    if not channel_id:
        raise IngestError("post_items called without a channel_id")
    if not items:
        return {"found": 0, "new": 0, "skipped": 0}

    endpoint = _endpoint()
    headers = _headers()
    totals = {"found": 0, "new": 0, "skipped": 0}

    for start in range(0, len(items), MAX_BATCH):
        batch = items[start:start + MAX_BATCH]
        result = _post_batch(endpoint, headers, channel_id, batch)
        for k in totals:
            totals[k] += int(result.get(k, 0) or 0)
        log.info(
            "channel %s batch %d-%d → found=%s new=%s skipped=%s",
            channel_id[:8], start, start + len(batch),
            result.get("found"), result.get("new"), result.get("skipped"),
        )
    return totals
