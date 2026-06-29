"""Full source registry table for the Sources screen (filterable)."""
from __future__ import annotations

from rich.text import Text
from textual.widgets import DataTable

from dashboard.widgets._render import (
    BLUE,
    DIM,
    EMERALD,
    GRAY,
    ORANGE,
    STATUS_LABEL,
    STATUS_STYLE,
)
from dashboard.widgets.health import effective_status


def _yn(flag: bool) -> Text:
    return Text("✓", style=EMERALD) if flag else Text("✗", style=ORANGE)


class SourceTable(DataTable):
    """All configured sources with reconciled health. Supports a text filter."""

    def __init__(self, telemetry, **kwargs) -> None:
        super().__init__(zebra_stripes=True, cursor_type="row", **kwargs)
        self._t = telemetry
        self._filter = ""

    def on_mount(self) -> None:
        self.add_column("Source", width=22)
        self.add_column("Category", width=12)
        self.add_column("Method", width=8)
        self.add_column("On", width=3)
        self.add_column("Verif", width=5)
        self.add_column("Wired", width=5)
        self.add_column("Fetched", width=8)
        self.add_column("Status", width=10)
        self.update_view()

    def set_filter(self, text: str) -> None:
        self._filter = text.lower().strip()
        self.update_view()

    def update_view(self) -> None:
        # preserve cursor position across refreshes
        prev = self.cursor_row
        self.clear()
        sources = sorted(self._t.sources(), key=lambda s: (not s.enabled, s.priority, s.name))
        log = self._t.log()
        q = self._filter
        for s in sources:
            if q and q not in s.name.lower() and q not in s.display_name.lower() \
                    and q not in s.category.lower():
                continue
            ls = log.sources.get(s.name)
            st = effective_status(s, ls.status if ls else "idle")
            fetched = ls.total_fetched if ls else 0
            kind_color = BLUE if s.kind == "social" else GRAY
            self.add_row(
                Text(s.display_name[:22], style=f"bold {kind_color}"),
                Text(s.category, style=GRAY),
                Text(s.method, style=GRAY),
                _yn(s.enabled),
                _yn(s.verified),
                _yn(s.wired),
                Text(str(fetched), style=EMERALD if fetched else DIM),
                Text(STATUS_LABEL.get(st, st.upper()), style=STATUS_STYLE.get(st, GRAY)),
            )
        if self.row_count and prev is not None:
            try:
                self.move_cursor(row=min(prev, self.row_count - 1))
            except Exception:
                pass
