"""A single cached entry point the UI talks to.

Widgets call ``app.telemetry.log()`` / ``.sources()`` / ``.metrics()`` once a
second. Parsing is cached on file mtime so a 1 Hz refresh stays cheap: the log
is only re-parsed when the collector actually writes to it.
"""
from __future__ import annotations

from dashboard.telemetry.logs import LogSnapshot, parse_log
from dashboard.telemetry.metrics import SystemMetrics, system_metrics
from dashboard.telemetry.paths import LOG_FILE, SOURCES_FILE
from dashboard.telemetry.sources import RegistrySummary, Source, load_sources, summarize


class Telemetry:
    """Mtime-cached facade over the node's local telemetry surfaces."""

    def __init__(self) -> None:
        self._log: LogSnapshot | None = None
        self._log_mtime: float = -1.0
        self._sources: list[Source] | None = None
        self._sources_mtime: float = -1.0
        # set by the live-capture worker; read by the Articles screen + feed.
        self.captured: list = []
        self.last_capture = None  # CaptureResult | None

    # ── source registry ────────────────────────────────────────────────
    def sources(self) -> list[Source]:
        mtime = SOURCES_FILE.stat().st_mtime if SOURCES_FILE.exists() else 0.0
        if self._sources is None or mtime != self._sources_mtime:
            self._sources = load_sources()
            self._sources_mtime = mtime
        return self._sources

    def registry(self) -> RegistrySummary:
        return summarize(self.sources())

    # ── collection log ─────────────────────────────────────────────────
    def log(self) -> LogSnapshot:
        mtime = LOG_FILE.stat().st_mtime if LOG_FILE.exists() else 0.0
        if self._log is None or mtime != self._log_mtime:
            snap = parse_log()
            # join per-category fetched counts using the registry
            cat_of = {s.name: s.category for s in self.sources()}
            per_cat: dict[str, int] = {}
            for st in snap.sources.values():
                cat = cat_of.get(st.name, "uncategorized")
                per_cat[cat] = per_cat.get(cat, 0) + st.total_fetched
            snap.per_category = per_cat
            self._log = snap
            self._log_mtime = mtime
        return self._log

    # ── host metrics (always live) ─────────────────────────────────────
    def metrics(self) -> SystemMetrics:
        return system_metrics()

    # ── force a re-read on next access ─────────────────────────────────
    def invalidate(self) -> None:
        self._log_mtime = -1.0
        self._sources_mtime = -1.0


__all__ = ["Telemetry"]
