"""Parse ``logs/collector.log`` into structured telemetry.

The collector logs in a fixed pipe-delimited format::

    2026-06-24 17:12:14,585 | INFO    | pipeline | [spa] ok — 25 fetched, 25 new (24847ms)

From the stream of lines we reconstruct collection runs, per-source outcomes,
errors, an activity feed, and the aggregates the analytics screen needs. The
parser tolerates both the current (``pipeline``) and legacy (``rawipress``)
message shapes so historical lines still count.
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

from dashboard.telemetry.paths import LOG_FILE

# ── line grammar ──────────────────────────────────────────────────────────
_LINE = re.compile(
    r"^(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),\d+ \| "
    r"(?P<level>\w+)\s*\| (?P<logger>[\w.\-]+) \| (?P<msg>.*)$"
)

# per-source outcome variants (newest first)
_RES_FETCHED = re.compile(
    r"^\[(?P<name>[^\]]+)\] ok — (?P<fetched>\d+) fetched, (?P<new>\d+) new \((?P<ms>\d+)ms\)"
)
_RES_SENT = re.compile(
    r"^\[(?P<name>[^\]]+)\] ok — (?P<sent>\d+) sent, found=(?P<found>\S+) "
    r"new=(?P<new>\S+) skipped=(?P<skipped>\S+)"
)
_RES_LEGACY = re.compile(r"^\[(?P<name>[^\]]+)\] (?P<fetched>\d+) fetched, (?P<new>\d+) new$")
_RES_DRY = re.compile(r"^\[(?P<name>[^\]]+)\] DRY-RUN — (?P<mapped>\d+) items mapped")
_RES_NOTHING = re.compile(r"^\[(?P<name>[^\]]+)\] nothing to send")

# run boundaries
_RUN_START = re.compile(r"=== (?P<run>run-\S+|collect run): (?P<count>\d+)")
_RUN_DONE = re.compile(r"=== run complete: (?:(?P<items>\d+) items, )?(?P<new>\d+) new")

_TS_FMT = "%Y-%m-%d %H:%M:%S"


@dataclass
class SourceStatus:
    name: str
    last_ts: datetime | None = None
    fetched: int = 0
    new: int = 0
    latency_ms: int | None = None
    ok: bool = True
    last_error: str = ""
    runs: int = 0
    total_fetched: int = 0
    total_new: int = 0

    @property
    def status(self) -> str:
        if self.last_ts is None:
            return "idle"
        if not self.ok:
            return "error"
        if self.fetched == 0:
            return "warning"
        return "online"


@dataclass
class FeedItem:
    ts: datetime
    name: str
    text: str
    level: str  # info | warning | error


@dataclass
class LogEvent:
    ts: datetime
    level: str
    logger: str
    msg: str


@dataclass
class LogSnapshot:
    """Everything the screens need, computed once per log change."""

    events: list[LogEvent] = field(default_factory=list)
    sources: dict[str, SourceStatus] = field(default_factory=dict)
    feed: list[FeedItem] = field(default_factory=list)
    runs: int = 0
    last_run_ts: datetime | None = None
    last_run_new: int = 0
    fetched_today: int = 0
    new_today: int = 0
    errors_today: int = 0
    # analytics aggregates
    per_hour: dict[str, int] = field(default_factory=dict)  # "YYYY-MM-DD HH" -> fetched
    per_category: dict[str, int] = field(default_factory=dict)  # filled by facade (needs registry)
    ok_results: int = 0
    failed_results: int = 0

    def top_sources(self, limit: int = 8) -> list[SourceStatus]:
        return sorted(
            self.sources.values(), key=lambda s: s.total_fetched, reverse=True
        )[:limit]

    @property
    def success_rate(self) -> float:
        total = self.ok_results + self.failed_results
        return (self.ok_results / total * 100.0) if total else 0.0


def _short(name: str) -> str:
    return name


def parse_log(path: Path = LOG_FILE, tail_lines: int = 4000) -> LogSnapshot:
    """Parse the (tail of the) collector log into a snapshot."""
    snap = LogSnapshot()
    if not path.exists():
        return snap

    try:
        raw = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return snap
    lines = raw[-tail_lines:]
    today = date.today()

    def stat(name: str) -> SourceStatus:
        return snap.sources.setdefault(name, SourceStatus(name=name))

    for line in lines:
        m = _LINE.match(line)
        if not m:
            continue
        try:
            ts = datetime.strptime(m["ts"], _TS_FMT)
        except ValueError:
            continue
        level = m["level"].lower()
        logger = m["logger"]
        msg = m["msg"]
        snap.events.append(LogEvent(ts, level, logger, msg))
        is_today = ts.date() == today

        # ── run boundaries ──────────────────────────────────────────────
        if (rs := _RUN_START.search(msg)):
            snap.runs += 1
            snap.last_run_ts = ts
            continue
        if (rd := _RUN_DONE.search(msg)):
            snap.last_run_ts = ts
            snap.last_run_new = int(rd["new"])
            continue

        # ── per-source outcomes ─────────────────────────────────────────
        matched = False
        if (r := _RES_FETCHED.match(msg)) or (r := _RES_LEGACY.match(msg)):
            name = r["name"]
            fetched, new = int(r["fetched"]), int(r["new"])
            ms = int(r["ms"]) if "ms" in r.groupdict() and r["ms"] else None
            s = stat(name)
            s.last_ts, s.fetched, s.new, s.ok = ts, fetched, new, True
            s.latency_ms = ms
            s.runs += 1
            s.total_fetched += fetched
            s.total_new += new
            snap.ok_results += 1
            snap.feed.append(FeedItem(ts, name, f"+{fetched} fetched · {new} new", "info"))
            hour = ts.strftime("%Y-%m-%d %H")
            snap.per_hour[hour] = snap.per_hour.get(hour, 0) + fetched
            if is_today:
                snap.fetched_today += fetched
                snap.new_today += new
            matched = True
        elif (r := _RES_SENT.match(msg)):
            name = r["name"]
            sent = int(r["sent"])
            new = int(r["new"]) if r["new"].isdigit() else 0
            s = stat(name)
            s.last_ts, s.fetched, s.new, s.ok = ts, sent, new, True
            s.runs += 1
            s.total_fetched += sent
            s.total_new += new
            snap.ok_results += 1
            snap.feed.append(FeedItem(ts, name, f"{sent} sent · {new} new", "info"))
            if is_today:
                snap.fetched_today += sent
                snap.new_today += new
            matched = True
        elif (r := _RES_DRY.match(msg)):
            name, mapped = r["name"], int(r["mapped"])
            s = stat(name)
            s.last_ts, s.fetched, s.ok = ts, mapped, True
            snap.feed.append(FeedItem(ts, name, f"dry-run · {mapped} mapped", "info"))
            matched = True
        elif _RES_NOTHING.match(msg):
            matched = True

        # ── errors / warnings on a collector.<name> logger ──────────────
        if not matched and logger.startswith("collector.") and level in ("error", "warning"):
            name = logger.split(".", 1)[1]
            s = stat(name)
            if level == "error":
                s.ok = False
                s.last_error = msg
                if is_today:
                    snap.errors_today += 1
            snap.feed.append(FeedItem(ts, name, msg, level))
        elif not matched and level == "error":
            if is_today:
                snap.errors_today += 1
            snap.feed.append(FeedItem(ts, logger, msg, "error"))

    snap.feed.sort(key=lambda f: f.ts, reverse=True)
    return snap


__all__ = ["LogSnapshot", "SourceStatus", "FeedItem", "LogEvent", "parse_log"]
