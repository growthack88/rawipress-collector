"""Captured-article table for the Articles screen.

Rows come from a live capture (``app.py dry-run``) stored on
``telemetry.captured`` — real headlines fetched from the live sources, not a
local archive.
"""
from __future__ import annotations

from rich.text import Text
from textual.widgets import DataTable

from dashboard.widgets._render import BLUE, DIM, EMERALD, GRAY


class CaptureFeed(DataTable):
    """Headlines from the most recent live capture, filterable."""

    def __init__(self, telemetry, **kwargs) -> None:
        super().__init__(zebra_stripes=True, cursor_type="row", **kwargs)
        self._t = telemetry
        self._filter = ""

    def on_mount(self) -> None:
        self.add_column("#", width=4)
        self.add_column("Headline", width=68)
        self.add_column("Source", width=18)
        self.add_column("Chars", width=7)
        self.update_view()

    def set_filter(self, text: str) -> None:
        self._filter = text.lower().strip()
        self.update_view()

    def current_article(self):
        idx = self.cursor_row
        rows = self._rows()
        if 0 <= idx < len(rows):
            return rows[idx]
        return None

    def _rows(self):
        q = self._filter
        items = self._t.captured
        if not q:
            return items
        return [a for a in items if q in a.title.lower() or q in a.source.lower()
                or q in a.body.lower()]

    def update_view(self) -> None:
        self.clear()
        rows = self._rows()
        for i, a in enumerate(rows, 1):
            self.add_row(
                Text(str(i), style=DIM),
                Text(a.title[:68] or "(untitled)", style=f"bold {GRAY}"),
                Text(a.source[:18], style=BLUE),
                Text(str(len(a.body)), style=EMERALD if a.body else DIM),
            )
