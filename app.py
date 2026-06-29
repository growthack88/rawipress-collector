#!/usr/bin/env python3
"""Rawi Press — Saudi Collector (CLI).

Push-only collector: fetches articles + X posts from inside KSA and POSTs the
raw items to the cloud `ingest` edge function. It does NOT store, summarize,
dedup, or render — the cloud pipeline does all of that.

Commands:
  python app.py collect             Collect news + social once, POST to ingest
  python app.py news                Collect news sources only
  python app.py social              Collect X/social channels only
  python app.py source <name>       Collect a single source/channel by name
  python app.py dry-run [name]      Map items to IngestItems and print JSON, no POST
  python app.py list                List configured sources + channels
  python app.py schedule [min]      Foreground auto-collector (default 15 min)

Secrets come from a gitignored .env (see .env.example).
"""
from __future__ import annotations

import json
import sys

from core import pipeline
from utils.logger import get_logger

log = get_logger("rawipress")


def _known_names() -> list[str]:
    return ([s["name"] for s in pipeline.load_sources()]
            + [s["name"] for s in pipeline.load_social()])


def cmd_collect() -> None:
    pipeline.run_collection()


def cmd_news() -> None:
    pipeline.run_collection(include_social=False)


def cmd_social() -> None:
    social_names = [s["name"] for s in pipeline.load_social()]
    if not social_names:
        log.info("no social channels configured")
        return
    pipeline.run_collection(source_names=social_names)


def cmd_source(name: str) -> None:
    if name not in _known_names():
        log.error("source '%s' not found. Known: %s", name, ", ".join(_known_names()))
        sys.exit(1)
    pipeline.run_collection([name])


def cmd_dry_run(name: str | None) -> None:
    names = [name] if name else None
    if name and name not in _known_names():
        log.error("source '%s' not found. Known: %s", name, ", ".join(_known_names()))
        sys.exit(1)
    result = pipeline.run_collection(names, dry_run=True)
    out = []
    for r in result["results"]:
        for item in r.get("items", []):
            out.append(item)
    print(json.dumps(out, ensure_ascii=False, indent=2))
    print(f"\n# {len(out)} IngestItems mapped (NOT posted)", file=sys.stderr)
    missing = [it["original_url"] for it in out if not it.get("body")]
    if missing:
        print(f"# WARNING: {len(missing)} item(s) have empty body", file=sys.stderr)


def cmd_list() -> None:
    print("news:")
    for s in pipeline.load_sources():
        flag = "on " if s.get("enabled", True) else "off"
        cid = "✓" if (s.get("channel_id") or "").strip() not in pipeline._PLACEHOLDERS else "✗"
        print(f"  [{flag}] chan:{cid} {s['name']:<16} {s.get('collection_method','?'):<8} {s.get('category','')}")
    print("social:")
    for s in pipeline.load_social():
        flag = "on " if s.get("enabled", True) else "off"
        cid = "✓" if (s.get("channel_id") or "").strip() not in pipeline._PLACEHOLDERS else "✗"
        print(f"  [{flag}] chan:{cid} {s['name']:<16} {s.get('platform','x'):<8} @{s.get('handle','')}")


def cmd_schedule(minutes: int = 15) -> None:
    """Dependency-free foreground scheduler (alternative to launchd)."""
    import time
    log.info("scheduler started — collecting every %d min (Ctrl-C to stop)", minutes)
    while True:
        try:
            pipeline.run_collection()
        except Exception:
            log.exception("scheduled run failed")
        time.sleep(max(1, minutes) * 60)


USAGE = ("usage: python app.py "
         "{collect | news | social | source <name> | dry-run [name] | list | schedule [min]}")


def main(argv: list[str]) -> None:
    if not argv:
        print(USAGE); sys.exit(1)
    cmd = argv[0]
    if cmd == "collect":
        cmd_collect()
    elif cmd == "news":
        cmd_news()
    elif cmd == "social":
        cmd_social()
    elif cmd == "source":
        if len(argv) < 2:
            print("usage: python app.py source <name>"); sys.exit(1)
        cmd_source(argv[1])
    elif cmd == "dry-run":
        cmd_dry_run(argv[1] if len(argv) > 1 else None)
    elif cmd == "list":
        cmd_list()
    elif cmd == "schedule":
        cmd_schedule(int(argv[1]) if len(argv) > 1 else 15)
    else:
        print(USAGE); sys.exit(1)


if __name__ == "__main__":
    main(sys.argv[1:])
