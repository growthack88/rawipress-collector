#!/usr/bin/env python3
"""Rawi Press — Saudi News Intelligence Platform (CLI).

Commands:
  python app.py collect             Collect every enabled source -> SQLite
  python app.py source <name>       Collect a single source
  python app.py status              Storage + source health summary
  python app.py list                List configured sources
  python app.py serve [host] [port] Run the dashboard + REST API (default 127.0.0.1:8787)
  python app.py initdb              Create the SQLite schema
  python app.py migrate [path]      Import a legacy data/raw_articles.json into SQLite

Pipeline: collect -> normalize -> enrich (intelligence) -> dedup-store (SQLite)
          -> per-source logs + health + daily stats.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from core import db, pipeline
from utils.logger import get_logger

ROOT = Path(__file__).resolve().parent
log = get_logger("rawipress")


def cmd_collect() -> None:
    pipeline.run_collection()


def cmd_source(name: str) -> None:
    names = [s["name"] for s in pipeline.load_sources()]
    if name not in names:
        log.error("source '%s' not found. Known: %s", name, ", ".join(names))
        sys.exit(1)
    pipeline.run_collection([name])


def cmd_status() -> None:
    db.init_db()
    conn = db.connect()
    try:
        stats = db.dashboard_stats(conn)
        sources = db.list_sources(conn)
    finally:
        conn.close()
    print("Rawi Press — status")
    print(f"  total articles : {stats['total_articles']}")
    print(f"  articles today : {stats['articles_today']}")
    print(f"  success rate   : {stats['success_rate']}%")
    print("  by source:")
    for name, count in stats["by_source"].items():
        print(f"    {name:<16} {count}")
    print("  by category:")
    for name, count in list(stats["by_category"].items())[:12]:
        print(f"    {name:<16} {count}")
    print("  source health:")
    for s in sources:
        print(f"    {s['name']:<16} {s.get('last_status') or 'idle':<6} "
              f"ok={s['success_count']} fail={s['failure_count']} total={s['total_collected']}")


def cmd_list() -> None:
    for s in pipeline.load_sources():
        flag = "on " if s.get("enabled", True) else "off"
        verified = "✓" if s.get("verified") else " "
        print(f"  [{flag}] {verified} {s['name']:<16} {s['collection_method']:<8} "
              f"p{s.get('priority','?')}  {s.get('category','')}")


def cmd_serve(host: str = "127.0.0.1", port: int = 8787) -> None:
    import uvicorn
    db.init_db()
    log.info("dashboard on http://%s:%s", host, port)
    uvicorn.run("web.server:app", host=host, port=port, log_level="info")


def cmd_schedule(minutes: int = 15) -> None:
    """Dependency-free foreground scheduler (alternative to launchd).
    Runs a collection now, then every <minutes>. Ctrl-C to stop."""
    import time
    log.info("scheduler started — collecting every %d min (Ctrl-C to stop)", minutes)
    while True:
        try:
            pipeline.run_collection()
        except Exception:
            log.exception("scheduled run failed")
        time.sleep(max(1, minutes) * 60)


def cmd_initdb() -> None:
    db.init_db()
    print(f"schema ready at {db.DB_PATH}")


def cmd_migrate(path: str | None = None) -> None:
    n = pipeline.migrate_json(path)
    print(f"migrated {n} legacy articles into {db.DB_PATH}")


USAGE = "usage: python app.py {collect | source <name> | status | list | serve [host] [port] | schedule [min] | initdb | migrate [path]}"


def main(argv: list[str]) -> None:
    if not argv:
        print(USAGE); sys.exit(1)
    cmd = argv[0]
    if cmd == "collect":
        cmd_collect()
    elif cmd == "source":
        if len(argv) < 2:
            print("usage: python app.py source <name>"); sys.exit(1)
        cmd_source(argv[1])
    elif cmd == "status":
        cmd_status()
    elif cmd == "list":
        cmd_list()
    elif cmd == "serve":
        host = argv[1] if len(argv) > 1 else "127.0.0.1"
        port = int(argv[2]) if len(argv) > 2 else 8787
        cmd_serve(host, port)
    elif cmd == "schedule":
        cmd_schedule(int(argv[1]) if len(argv) > 1 else 15)
    elif cmd == "initdb":
        cmd_initdb()
    elif cmd == "migrate":
        cmd_migrate(argv[1] if len(argv) > 1 else None)
    else:
        print(USAGE); sys.exit(1)


if __name__ == "__main__":
    main(sys.argv[1:])
