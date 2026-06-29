"""Live activity feed — newest-first stream synthesised from the log."""
from __future__ import annotations

from rich.table import Table
from rich.text import Text
from textual.widget import Widget

from dashboard.widgets._render import DIM, GRAY, LEVEL_STYLE


class ActivityFeed(Widget):
    """Scrolling ops feed: timestamp · source · event, colour-coded by level."""

    DEFAULT_CSS = """
    ActivityFeed { height: 1fr; }
    """

    def __init__(self, telemetry, limit: int = 16, **kwargs) -> None:
        super().__init__(**kwargs)
        self._t = telemetry
        self._limit = limit

    def on_mount(self) -> None:
        self.update_view()

    def update_view(self) -> None:
        self.refresh()

    def render(self):
        log = self._t.log()
        table = Table.grid(expand=True, padding=(0, 1))
        table.add_column(width=8, no_wrap=True)   # time
        table.add_column(width=14, no_wrap=True)  # source
        table.add_column(ratio=1)                 # text

        items = log.feed[: self._limit]
        if not items:
            table.add_row(Text("—", style=DIM), Text("system", style=GRAY),
                          Text("no collection activity yet — press R to collect", style=DIM))
            return table

        for f in items:
            color = LEVEL_STYLE.get(f.level, GRAY)
            table.add_row(
                Text(f.ts.strftime("%H:%M:%S"), style=DIM),
                Text(f.name[:14], style=f"bold {color}"),
                Text(f.text, style=GRAY, overflow="ellipsis"),
            )
        return table
