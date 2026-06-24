"""Persistence for collected articles.

MVP storage is a single JSON array at data/raw_articles.json, written
atomically (temp file + os.replace) so a crash mid-write never corrupts
the store. Phase 2 swaps this module for Postgres/Supabase without
touching collectors.
"""
import json
import os
import tempfile
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
ARTICLES_FILE = DATA_DIR / "raw_articles.json"


def _atomic_write(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def load_articles() -> list:
    if not ARTICLES_FILE.exists():
        return []
    try:
        with open(ARTICLES_FILE, encoding="utf-8") as fh:
            return json.load(fh)
    except (json.JSONDecodeError, OSError):
        return []


def save_articles(articles: list) -> None:
    _atomic_write(ARTICLES_FILE, articles)


def append_articles(new_items: list) -> int:
    """Append already-deduplicated items to the store. Returns count added."""
    if not new_items:
        return 0
    articles = load_articles()
    articles.extend(new_items)
    save_articles(articles)
    return len(new_items)


def stats() -> dict:
    articles = load_articles()
    by_source: dict = {}
    for a in articles:
        by_source[a.get("source", "?")] = by_source.get(a.get("source", "?"), 0) + 1
    return {"total": len(articles), "by_source": by_source}
