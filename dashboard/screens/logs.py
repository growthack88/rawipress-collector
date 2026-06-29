"""Logs screen — a live, colour-coded tail of the parsed collector log."""
from __future__ import annotations

from rich.table import Table
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widget import Widget
from textual.widgets import Footer

from dashboard.screens.base import RefreshableScreen
from dashboard.widgets._render import BLUE, DIM, EMERALD, GRAY, ORANGE, RED
from dashboard.widgets.card import Card

_LEVEL = {"info": EMERALD, "warning": ORANGE, "error": RED, "debug": DIM}


class LogView(Widget):
    """Renders the tail of parsed log events, newest at the bottom."""

    DEFAULT_CSS = "LogView { height: auto; }"

    def __init__(self, telemetry, limit: int = 300, **kwargs) -> None:
        super().__init__(**kwargs)
        self._t = telemetry
        self._limit = limit

    def on_mount(self) -> None:
        self.update_view()

    def update_view(self) -> None:
        self.refresh()

    def render(self):
        events = self._t.log().events[-self._limit:]
        table = Table.grid(expand=True, padding=(0, 1))
        table.add_column(width=9, no_wrap=True)   # time
        table.add_column(width=8, no_wrap=True)   # level
        table.add_column(width=18, no_wrap=True)  # logger
        table.add_column(ratio=1)                 # message
        if not events:
            table.add_row(Text("—", style=DIM), Text("", style=DIM),
                          Text("collector.log", style=GRAY),
                          Text("no log entries yet", style=DIM))
            return table
        for e in events:
            color = _LEVEL.get(e.level, GRAY)
            table.add_row(
                Text(e.ts.strftime("%H:%M:%S"), style=DIM),
                Text(e.level.upper(), style=f"bold {color}"),
                Text(e.logger[:18], style=BLUE),
                Text(e.msg, style=GRAY, overflow="ellipsis"),
            )
        return table


class LogsScreen(RefreshableScreen):
    def compose(self) -> ComposeResult:
        with Card(title="COLLECTOR LOG", subtitle="logs/collector.log · live tail", id="logs-card"):
            with VerticalScroll(id="logs-scroll"):
                yield LogView(self.telemetry)
        yield Footer()

    def on_mount(self) -> None:
        super().on_mount()
        self._autoscroll()

    def _on_tick(self) -> None:
        super()._on_tick()
        self._autoscroll()

    def _autoscroll(self) -> None:
        try:
            self.query_one("#logs-scroll", VerticalScroll).scroll_end(animate=False)
        except Exception:
            pass
