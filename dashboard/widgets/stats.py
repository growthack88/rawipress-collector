"""Live statistics grid — node + registry + run + host metrics."""
from __future__ import annotations

from textual.widget import Widget

from dashboard.widgets._render import (
    BLUE,
    EMERALD,
    GRAY,
    ORANGE,
    RED,
    stat_grid,
)


class StatsGrid(Widget):
    """A grid of stat tiles, refreshed from telemetry on each tick."""

    DEFAULT_CSS = """
    StatsGrid { height: auto; }
    """

    def __init__(self, telemetry, columns: int = 4, **kwargs) -> None:
        super().__init__(**kwargs)
        self._t = telemetry
        self._columns = columns

    def on_mount(self) -> None:
        self.update_view()

    def update_view(self) -> None:
        self.refresh()

    def render(self):
        t = self._t
        reg = t.registry()
        log = t.log()
        m = t.metrics()
        top = log.top_sources(1)
        top_name = top[0].name if top else "—"

        def col(v: int, warn_if_zero: bool = False) -> str:
            return ORANGE if (warn_if_zero and v == 0) else EMERALD

        tiles = [
            ("Sources", str(reg.total), EMERALD),
            ("Enabled", str(reg.enabled), EMERALD),
            ("Verified", str(reg.verified), col(reg.verified, True)),
            ("Wired", str(reg.wired), col(reg.wired, True)),

            ("Runs", str(log.runs), BLUE),
            ("Fetched Today", str(log.fetched_today), col(log.fetched_today, True)),
            ("New Today", str(log.new_today), col(log.new_today, True)),
            ("Errors Today", str(log.errors_today), RED if log.errors_today else EMERALD),

            ("Success", f"{log.success_rate:.0f}%",
             EMERALD if log.success_rate >= 80 else ORANGE if log.success_rate >= 50 else RED),
            ("Top Source", top_name, EMERALD),
            ("News / Social", f"{reg.news}/{reg.social}", BLUE),
            ("Sent Cache", str(m.sent_cache.count) if m.sent_cache.enabled else "off",
             EMERALD if m.sent_cache.enabled else GRAY),

            ("CPU", f"{m.cpu_percent:.0f}%",
             EMERALD if m.cpu_percent < 70 else ORANGE if m.cpu_percent < 90 else RED),
            ("Memory", f"{m.mem_percent:.0f}%",
             EMERALD if m.mem_percent < 70 else ORANGE if m.mem_percent < 90 else RED),
            ("Node Uptime", m.proc_uptime, BLUE),
            ("Log Size", m.log_size, GRAY),
        ]
        return stat_grid(tiles, columns=self._columns)
