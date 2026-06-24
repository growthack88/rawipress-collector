"""Collection pipeline (Phases 1+2+3+8 orchestration).

collect -> normalize -> enrich -> dedup-store(SQLite) -> log + health + stats.

Per-source failures are isolated and recorded in collection_logs; one bad
source never aborts a run. Deduplication is enforced by the UNIQUE hash
(canonical URL) constraint in the articles table.
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

from collectors import build_collector
from core import db
from core.enrich import enrich
from utils.logger import get_logger
from utils.parser import normalize

ROOT = Path(__file__).resolve().parent.parent
SOURCES_FILE = ROOT / "config" / "sources.json"
log = get_logger("pipeline")


def load_sources() -> list[dict]:
    with open(SOURCES_FILE, encoding="utf-8") as fh:
        return json.load(fh).get("sources", [])


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def run_source(conn, source: dict, run_id: str) -> dict:
    name = source.get("name", "?")
    started = _now()
    t0 = time.time()
    fetched, new_count, status, error = 0, 0, "ok", ""

    if not source.get("enabled", True):
        return {"source": name, "skipped": True, "new": 0}

    try:
        raw_items = build_collector(source).collect()
        normalized = [normalize(r, source) for r in raw_items if r.get("url")]
        fetched = len(normalized)
        for item in normalized:
            item["hash"] = item["id"]
            enrich(item, source)
            if db.insert_article(conn, item):
                new_count += 1
    except Exception as exc:
        status, error = "error", f"{type(exc).__name__}: {exc}"
        log.exception("[%s] collector failed", name)

    finished = _now()
    duration_ms = int((time.time() - t0) * 1000)
    db.insert_log(conn, {
        "run_id": run_id, "source": name, "started_at": started,
        "finished_at": finished, "duration_ms": duration_ms,
        "fetched": fetched, "new_count": new_count, "status": status, "error": error,
    })
    db.record_source_run(conn, name, status=status, new_count=new_count, error=error)
    conn.commit()
    log.info("[%s] %s — %d fetched, %d new (%dms)", name, status, fetched, new_count, duration_ms)
    return {"source": name, "status": status, "fetched": fetched, "new": new_count, "error": error}


def run_collection(source_names: list[str] | None = None) -> dict:
    db.init_db()
    sources = load_sources()
    conn = db.connect()
    try:
        for s in sources:
            db.upsert_source(conn, s)
        conn.commit()

        if source_names:
            wanted = set(source_names)
            sources = [s for s in sources if s.get("name") in wanted]

        run_id = datetime.now(timezone.utc).strftime("run-%Y%m%dT%H%M%SZ")
        log.info("=== %s: %d sources ===", run_id, len(sources))
        results = [run_source(conn, s, run_id) for s in sources]

        db.snapshot_daily(conn)
        conn.commit()
    finally:
        conn.close()

    total_new = sum(r.get("new", 0) for r in results)
    log.info("=== run complete: %d new articles ===", total_new)
    return {"run_id": run_id, "total_new": total_new, "results": results}


def migrate_json(json_path: str | None = None) -> int:
    """Import a legacy data/raw_articles.json into SQLite (one-time)."""
    path = Path(json_path) if json_path else ROOT / "data" / "raw_articles.json"
    if not path.exists():
        log.info("no legacy json at %s", path)
        return 0
    db.init_db()
    with open(path, encoding="utf-8") as fh:
        articles = json.load(fh)
    conn = db.connect()
    imported = 0
    try:
        for a in articles:
            a["hash"] = a.get("id") or a.get("hash")
            if not a.get("hash"):
                continue
            enrich(a)  # backfill intelligence fields
            if db.insert_article(conn, a):
                imported += 1
        conn.commit()
    finally:
        conn.close()
    log.info("migrated %d legacy articles", imported)
    return imported
