#!/usr/bin/env python3
"""Rawi Press — Saudi Intelligence Collection Engine (CLI).

Commands:
  python app.py collect            Run every enabled source once
  python app.py source <name>      Run a single source by name
  python app.py status             Show storage + source registry summary
  python app.py list               List configured sources

The engine: load registry -> for each source build the right collector by
collection_method -> collect() raw items -> normalize -> dedupe -> store.
Per-source failures are logged and isolated; one bad source never aborts a run.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from collectors import build_collector
from utils.deduplicator import Deduplicator
from utils.logger import get_logger
from utils.parser import normalize
from utils import storage

ROOT = Path(__file__).resolve().parent
SOURCES_FILE = ROOT / "config" / "sources.json"

log = get_logger("rawipress")


def load_sources() -> list[dict]:
    with open(SOURCES_FILE, encoding="utf-8") as fh:
        return json.load(fh).get("sources", [])


def run_source(source: dict, dedup: Deduplicator) -> int:
    """Collect one source. Returns number of NEW items stored."""
    name = source.get("name", "?")
    if not source.get("enabled", True):
        log.info("[%s] disabled, skipping", name)
        return 0
    try:
        collector = build_collector(source)
        raw_items = collector.collect()
    except Exception as exc:  # isolate per-source failures
        log.exception("[%s] collector crashed: %s", name, exc)
        return 0

    normalized = [normalize(r, source) for r in raw_items if r.get("url")]
    fresh = dedup.filter_new(normalized)
    added = storage.append_articles(fresh)
    log.info("[%s] %d fetched, %d new", name, len(normalized), added)
    return added


def cmd_collect() -> None:
    sources = load_sources()
    dedup = Deduplicator()
    total = 0
    log.info("=== collect run: %d sources ===", len(sources))
    for source in sources:
        total += run_source(source, dedup)
    dedup.save()
    log.info("=== run complete: %d new items ===", total)


def cmd_source(name: str) -> None:
    sources = load_sources()
    match = next((s for s in sources if s.get("name") == name), None)
    if not match:
        log.error("source '%s' not found. Known: %s", name, ", ".join(s["name"] for s in sources))
        sys.exit(1)
    dedup = Deduplicator()
    run_source(match, dedup)
    dedup.save()


def cmd_status() -> None:
    sources = load_sources()
    st = storage.stats()
    print("Rawi Press — status")
    print(f"  stored articles: {st['total']}")
    print("  by source:")
    for name, count in sorted(st["by_source"].items(), key=lambda x: -x[1]):
        print(f"    {name:<16} {count}")
    enabled = sum(1 for s in sources if s.get("enabled", True))
    print(f"  sources configured: {len(sources)} ({enabled} enabled)")


def cmd_list() -> None:
    for s in load_sources():
        flag = "on " if s.get("enabled", True) else "off"
        verified = "✓" if s.get("verified") else " "
        print(f"  [{flag}] {verified} {s['name']:<16} {s['collection_method']:<8} p{s.get('priority','?')}  {s.get('category','')}")


USAGE = "usage: python app.py {collect | source <name> | status | list}"


def main(argv: list[str]) -> None:
    if not argv:
        print(USAGE)
        sys.exit(1)
    cmd = argv[0]
    if cmd == "collect":
        cmd_collect()
    elif cmd == "source":
        if len(argv) < 2:
            print("usage: python app.py source <name>")
            sys.exit(1)
        cmd_source(argv[1])
    elif cmd == "status":
        cmd_status()
    elif cmd == "list":
        cmd_list()
    else:
        print(USAGE)
        sys.exit(1)


if __name__ == "__main__":
    main(sys.argv[1:])
