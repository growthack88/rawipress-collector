"""SQLite storage layer for Rawi Press (Phase 2).

Replaces the JSON store. Four tables: articles, sources, collection_logs,
statistics. WAL mode so the dashboard can read while the collector writes.

All access goes through this module — the rest of the app never touches SQL.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone, date
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DB_PATH = DATA_DIR / "rawipress.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS articles (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    hash             TEXT UNIQUE NOT NULL,
    source           TEXT NOT NULL,
    title            TEXT,
    url              TEXT NOT NULL,
    content          TEXT,
    summary          TEXT,
    published_at     TEXT,
    collected_at     TEXT,
    category         TEXT,
    language         TEXT,
    tags             TEXT,            -- JSON array
    keywords         TEXT,            -- JSON array
    entities         TEXT,            -- JSON object {organizations, people, locations}
    author           TEXT,
    sentiment        TEXT,            -- positive | negative | neutral
    importance_score REAL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_articles_source       ON articles(source);
CREATE INDEX IF NOT EXISTS idx_articles_published    ON articles(published_at);
CREATE INDEX IF NOT EXISTS idx_articles_category     ON articles(category);
CREATE INDEX IF NOT EXISTS idx_articles_language     ON articles(language);
CREATE INDEX IF NOT EXISTS idx_articles_collected    ON articles(collected_at);

CREATE TABLE IF NOT EXISTS sources (
    name              TEXT PRIMARY KEY,
    display_name      TEXT,
    category          TEXT,
    url               TEXT,
    method            TEXT,
    priority          INTEGER,
    enabled           INTEGER DEFAULT 1,
    last_collected_at TEXT,
    last_status       TEXT,           -- ok | error
    last_error        TEXT,
    total_collected   INTEGER DEFAULT 0,
    success_count     INTEGER DEFAULT 0,
    failure_count     INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS collection_logs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id      TEXT,
    source      TEXT,
    started_at  TEXT,
    finished_at TEXT,
    duration_ms INTEGER,
    fetched     INTEGER DEFAULT 0,
    new_count   INTEGER DEFAULT 0,
    status      TEXT,                 -- ok | error
    error       TEXT
);
CREATE INDEX IF NOT EXISTS idx_logs_run    ON collection_logs(run_id);
CREATE INDEX IF NOT EXISTS idx_logs_source ON collection_logs(source);

CREATE TABLE IF NOT EXISTS statistics (
    day          TEXT PRIMARY KEY,    -- YYYY-MM-DD
    total        INTEGER,
    by_source    TEXT,                -- JSON
    by_category  TEXT,                -- JSON
    by_language  TEXT,                -- JSON
    computed_at  TEXT
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def connect() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=10000;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


def init_db() -> None:
    conn = connect()
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------- articles ---
ARTICLE_FIELDS = (
    "hash", "source", "title", "url", "content", "summary", "published_at",
    "collected_at", "category", "language", "tags", "keywords", "entities",
    "author", "sentiment", "importance_score",
)


def _row_to_article(row: sqlite3.Row) -> dict:
    d = dict(row)
    for jf in ("tags", "keywords", "entities"):
        if d.get(jf):
            try:
                d[jf] = json.loads(d[jf])
            except (json.JSONDecodeError, TypeError):
                pass
    return d


def insert_article(conn: sqlite3.Connection, item: dict) -> bool:
    """Insert one enriched article. Returns True if new, False if duplicate hash."""
    payload = {k: item.get(k) for k in ARTICLE_FIELDS}
    for jf in ("tags", "keywords", "entities"):
        if isinstance(payload.get(jf), (list, dict)):
            payload[jf] = json.dumps(payload[jf], ensure_ascii=False)
    cols = ", ".join(ARTICLE_FIELDS)
    placeholders = ", ".join(f":{k}" for k in ARTICLE_FIELDS)
    try:
        conn.execute(
            f"INSERT INTO articles ({cols}) VALUES ({placeholders})", payload
        )
        return True
    except sqlite3.IntegrityError:
        return False  # duplicate hash


def get_article(conn: sqlite3.Connection, article_id: int) -> dict | None:
    row = conn.execute("SELECT * FROM articles WHERE id = ?", (article_id,)).fetchone()
    return _row_to_article(row) if row else None


def list_articles(
    conn: sqlite3.Connection,
    *,
    q: str = "",
    source: str = "",
    category: str = "",
    language: str = "",
    date_from: str = "",
    date_to: str = "",
    sort: str = "collected_at",
    order: str = "desc",
    limit: int = 25,
    offset: int = 0,
) -> tuple[list[dict], int]:
    where, params = [], {}
    if q:
        where.append("(title LIKE :q OR content LIKE :q OR keywords LIKE :q)")
        params["q"] = f"%{q}%"
    if source:
        where.append("source = :source"); params["source"] = source
    if category:
        where.append("category = :category"); params["category"] = category
    if language:
        where.append("language = :language"); params["language"] = language
    if date_from:
        where.append("COALESCE(published_at, collected_at) >= :df"); params["df"] = date_from
    if date_to:
        where.append("COALESCE(published_at, collected_at) <= :dt"); params["dt"] = date_to
    clause = (" WHERE " + " AND ".join(where)) if where else ""

    sort = sort if sort in {"collected_at", "published_at", "importance_score", "source"} else "collected_at"
    order = "ASC" if str(order).lower() == "asc" else "DESC"

    total = conn.execute(f"SELECT COUNT(*) FROM articles{clause}", params).fetchone()[0]
    params["limit"], params["offset"] = max(1, min(limit, 200)), max(0, offset)
    rows = conn.execute(
        f"SELECT * FROM articles{clause} ORDER BY {sort} {order} LIMIT :limit OFFSET :offset",
        params,
    ).fetchall()
    return [_row_to_article(r) for r in rows], total


# ----------------------------------------------------------------- sources ---
def upsert_source(conn: sqlite3.Connection, src: dict) -> None:
    conn.execute(
        """
        INSERT INTO sources (name, display_name, category, url, method, priority, enabled)
        VALUES (:name, :display_name, :category, :url, :method, :priority, :enabled)
        ON CONFLICT(name) DO UPDATE SET
            display_name=excluded.display_name, category=excluded.category,
            url=excluded.url, method=excluded.method, priority=excluded.priority,
            enabled=excluded.enabled
        """,
        {
            "name": src.get("name"),
            "display_name": src.get("display_name", src.get("name")),
            "category": src.get("category", ""),
            "url": src.get("source_url", ""),
            "method": src.get("collection_method", ""),
            "priority": src.get("priority", 3),
            "enabled": 1 if src.get("enabled", True) else 0,
        },
    )


def record_source_run(
    conn: sqlite3.Connection, name: str, *, status: str, new_count: int, error: str = ""
) -> None:
    ok = 1 if status == "ok" else 0
    conn.execute(
        """
        UPDATE sources SET
            last_collected_at = ?,
            last_status = ?,
            last_error = ?,
            total_collected = total_collected + ?,
            success_count = success_count + ?,
            failure_count = failure_count + ?
        WHERE name = ?
        """,
        (_now(), status, error[:500], new_count, ok, 0 if ok else 1, name),
    )


def list_sources(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute("SELECT * FROM sources ORDER BY priority, name").fetchall()
    return [dict(r) for r in rows]


# -------------------------------------------------------------------- logs ---
def insert_log(conn: sqlite3.Connection, log: dict) -> None:
    conn.execute(
        """
        INSERT INTO collection_logs
            (run_id, source, started_at, finished_at, duration_ms, fetched, new_count, status, error)
        VALUES (:run_id, :source, :started_at, :finished_at, :duration_ms, :fetched, :new_count, :status, :error)
        """,
        {
            "run_id": log.get("run_id"), "source": log.get("source"),
            "started_at": log.get("started_at"), "finished_at": log.get("finished_at"),
            "duration_ms": log.get("duration_ms", 0), "fetched": log.get("fetched", 0),
            "new_count": log.get("new_count", 0), "status": log.get("status", "ok"),
            "error": (log.get("error") or "")[:1000],
        },
    )


def list_logs(conn: sqlite3.Connection, limit: int = 100) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM collection_logs ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    return [dict(r) for r in rows]


# --------------------------------------------------------------- analytics ---
def _count_by(conn: sqlite3.Connection, column: str) -> dict:
    rows = conn.execute(
        f"SELECT COALESCE(NULLIF({column}, ''), 'unknown') k, COUNT(*) c "
        f"FROM articles GROUP BY k ORDER BY c DESC"
    ).fetchall()
    return {r["k"]: r["c"] for r in rows}


def dashboard_stats(conn: sqlite3.Connection) -> dict:
    total = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
    today = date.today().isoformat()
    today_count = conn.execute(
        "SELECT COUNT(*) FROM articles WHERE substr(collected_at,1,10) = ?", (today,)
    ).fetchone()[0]
    by_source = _count_by(conn, "source")
    by_category = _count_by(conn, "category")
    by_language = _count_by(conn, "language")

    # collection success rate from logs
    log_row = conn.execute(
        "SELECT SUM(CASE WHEN status='ok' THEN 1 ELSE 0 END) ok, COUNT(*) total FROM collection_logs"
    ).fetchone()
    runs_total = log_row["total"] or 0
    success_rate = round(100.0 * (log_row["ok"] or 0) / runs_total, 1) if runs_total else 0.0

    return {
        "total_articles": total,
        "articles_today": today_count,
        "sources_count": conn.execute("SELECT COUNT(*) FROM sources").fetchone()[0],
        "success_rate": success_rate,
        "top_sources": list(by_source.items())[:8],
        "top_categories": list(by_category.items())[:8],
        "by_source": by_source,
        "by_category": by_category,
        "by_language": by_language,
    }


def articles_by_day(conn: sqlite3.Connection, days: int = 14) -> dict:
    rows = conn.execute(
        """
        SELECT substr(COALESCE(published_at, collected_at),1,10) d, COUNT(*) c
        FROM articles GROUP BY d ORDER BY d DESC LIMIT ?
        """,
        (days,),
    ).fetchall()
    return {r["d"]: r["c"] for r in reversed(rows) if r["d"]}


def trending_keywords(conn: sqlite3.Connection, limit: int = 25) -> list[tuple[str, int]]:
    counts: dict[str, int] = {}
    for (kw_json,) in conn.execute("SELECT keywords FROM articles WHERE keywords IS NOT NULL"):
        try:
            for kw in json.loads(kw_json):
                counts[kw] = counts.get(kw, 0) + 1
        except (json.JSONDecodeError, TypeError):
            continue
    return sorted(counts.items(), key=lambda x: -x[1])[:limit]


def top_entities(conn: sqlite3.Connection, limit: int = 20) -> dict:
    buckets = {"organizations": {}, "people": {}, "locations": {}}
    for (ent_json,) in conn.execute("SELECT entities FROM articles WHERE entities IS NOT NULL"):
        try:
            ent = json.loads(ent_json)
        except (json.JSONDecodeError, TypeError):
            continue
        for k in buckets:
            for name in ent.get(k, []):
                buckets[k][name] = buckets[k].get(name, 0) + 1
    return {
        k: sorted(v.items(), key=lambda x: -x[1])[:limit] for k, v in buckets.items()
    }


def snapshot_daily(conn: sqlite3.Connection) -> None:
    """Persist today's aggregate into the statistics table."""
    stats = dashboard_stats(conn)
    conn.execute(
        """
        INSERT INTO statistics (day, total, by_source, by_category, by_language, computed_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(day) DO UPDATE SET
            total=excluded.total, by_source=excluded.by_source,
            by_category=excluded.by_category, by_language=excluded.by_language,
            computed_at=excluded.computed_at
        """,
        (
            date.today().isoformat(), stats["total_articles"],
            json.dumps(stats["by_source"], ensure_ascii=False),
            json.dumps(stats["by_category"], ensure_ascii=False),
            json.dumps(stats["by_language"], ensure_ascii=False),
            _now(),
        ),
    )
