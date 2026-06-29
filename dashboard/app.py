#!/usr/bin/env python3
"""RawiPress Terminal OS — fullscreen Textual operations center for the
Saudi collector node.

    cd ~/Documents/RawiPress
    source .venv/bin/activate
    python dashboard/app.py

All data is real and local: the source registry, the collection log, the
sent-cache, live captures, and host metrics. The node stores no article
database (it is push-only), so this is a monitoring console for the box itself.
"""
from __future__ import annotations

import sys
from pathlib import Path

# allow `python dashboard/app.py` to import the `dashboard` package
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from textual import work  # noqa: E402
from textual.app import App  # noqa: E402
from textual.theme import Theme  # noqa: E402

from dashboard.screens.analytics import AnalyticsScreen  # noqa: E402
from dashboard.screens.articles import ArticlesScreen  # noqa: E402
from dashboard.screens.dashboard import DashboardScreen  # noqa: E402
from dashboard.screens.logs import LogsScreen  # noqa: E402
from dashboard.screens.search import SearchScreen  # noqa: E402
from dashboard.screens.settings import SettingsScreen  # noqa: E402
from dashboard.screens.sources import SourcesScreen  # noqa: E402
from dashboard.telemetry import Telemetry  # noqa: E402
from dashboard.telemetry.collector import run_capture as run_capture_job  # noqa: E402

RAWI_THEME = Theme(
    name="rawi",
    primary="#22C55E",
    secondary="#0EA5E9",
    accent="#0EA5E9",
    foreground="#E4E4E7",
    background="#09090B",
    surface="#111114",
    panel="#16161A",
    success="#22C55E",
    warning="#F59E0B",
    error="#EF4444",
    dark=True,
    variables={"gray": "#A1A1AA", "orange": "#F59E0B"},
)

_MODES = {
    "dashboard": DashboardScreen,
    "articles": ArticlesScreen,
    "sources": SourcesScreen,
    "logs": LogsScreen,
    "analytics": AnalyticsScreen,
    "settings": SettingsScreen,
}


class RawiTerminalApp(App):
    CSS_PATH = "css/rawi.tcss"
    TITLE = "RAWI PRESS — Terminal OS"
    SUB_TITLE = "Saudi Intelligence Operations Center"

    BINDINGS = [
        ("d", "nav('dashboard')", "Dashboard"),
        ("a", "nav('articles')", "Articles"),
        ("s", "nav('sources')", "Sources"),
        ("l", "nav('logs')", "Logs"),
        ("t", "nav('analytics')", "Analytics"),
        ("g", "nav('settings')", "Settings"),
        ("slash", "search", "Search"),
        ("r", "collect", "Collect"),
        ("f", "refresh", "Refresh"),
        ("q", "quit", "Quit"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.telemetry = Telemetry()
        # capture state lives on telemetry so every screen can read it
        self.telemetry.capture_running = False
        self.telemetry.capture_target = None
        self.telemetry.last_capture = None

    def on_mount(self) -> None:
        self.register_theme(RAWI_THEME)
        self.theme = "rawi"
        for name, screen_cls in _MODES.items():
            self.add_mode(name, (lambda c=screen_cls: c(self.telemetry)))
        self.switch_mode("dashboard")

    # ── navigation ─────────────────────────────────────────────────────
    def action_nav(self, mode: str) -> None:
        if self.current_mode != mode:
            self.switch_mode(mode)

    def action_refresh(self) -> None:
        self.telemetry.invalidate()
        screen = self.screen
        tick = getattr(screen, "_on_tick", None)
        if tick:
            tick()
        self.notify("Telemetry refreshed", timeout=2)

    # ── search ─────────────────────────────────────────────────────────
    def action_search(self) -> None:
        self.push_screen(SearchScreen(), self._apply_search)

    def _apply_search(self, query: str | None) -> None:
        if not query:
            return
        if self.current_mode not in ("sources", "articles"):
            self.switch_mode("sources")
        self.call_after_refresh(self._deliver_query, query)

    def _deliver_query(self, query: str) -> None:
        apply = getattr(self.screen, "apply_filter", None)
        if apply:
            apply(query)
            self.notify(f"Filter: “{query}”", timeout=2)

    # ── live capture (background thread worker) ────────────────────────
    def action_collect(self) -> None:
        if self.telemetry.capture_running:
            self.notify("A capture is already running…", timeout=2)
            return
        self.run_capture(None)

    @work(thread=True, exclusive=True, group="capture")
    def run_capture(self, source: str | None) -> None:
        self.telemetry.capture_running = True
        self.telemetry.capture_target = source or "all"
        self.call_from_thread(
            self.notify, f"Capturing {source or 'all sources'} — live fetch…", timeout=3
        )
        result = run_capture_job(source)
        self.telemetry.captured = result.articles
        self.telemetry.last_capture = result
        self.telemetry.capture_running = False
        if result.ok:
            msg, sev = f"Captured {len(result.articles)} items from {result.target}", "information"
        else:
            msg, sev = f"Capture failed: {result.error}", "warning"
        self.call_from_thread(self.notify, msg, severity=sev, timeout=4)


def main() -> None:
    RawiTerminalApp().run()


if __name__ == "__main__":
    main()
