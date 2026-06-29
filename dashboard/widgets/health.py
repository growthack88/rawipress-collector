"""Source health panel — colour-coded ONLINE / WARNING / OFFLINE per source.

Combines two real signals: the registry's configured state (enabled / verified
/ wired) and the log's last observed outcome (ok / error / fetched count).
"""
from __future__ import annotations

from rich.table import Table
from rich.text import Text
from textual.widget import Widget

from dashboard.widgets._render import DIM, GRAY, STATUS_LABEL, STATUS_STYLE, DOT


def effective_status(source, log_status) -> str:
    """Reconcile config status with the last observed run outcome."""
    if not source.enabled:
        return "offline"
    if log_status == "error":
        return "error"
    if not source.verified or not source.wired:
        return "warning"
    if log_status in ("online", "warning", "error", "idle"):
        return log_status
    return "idle"


class SourceHealth(Widget):
    """Compact, priority-sorted health list for the dashboard sidebar."""

    DEFAULT_CSS = """
    SourceHealth { height: 1fr; }
    """

    def __init__(self, telemetry, limit: int = 14, **kwargs) -> None:
        super().__init__(**kwargs)
        self._t = telemetry
        self._limit = limit

    def on_mount(self) -> None:
        self.update_view()

    def update_view(self) -> None:
        self.refresh()

    def render(self):
        sources = sorted(self._t.sources(), key=lambda s: (s.priority, s.name))
        log = self._t.log()
        table = Table.grid(expand=True, padding=(0, 1))
        table.add_column(ratio=1)            # name
        table.add_column(justify="right")    # status

        shown = [s for s in sources if s.kind == "news"][: self._limit]
        for s in shown:
            ls = log.sources.get(s.name)
            st = effective_status(s, ls.status if ls else "idle")
            color = STATUS_STYLE.get(st, GRAY)
            name = Text(s.display_name[:22], style=GRAY)
            badge = Text(f"{DOT} {STATUS_LABEL.get(st, st.upper())}", style=color)
            table.add_row(name, badge)
        if not shown:
            table.add_row(Text("no sources configured", style=DIM), Text(""))
        return table
