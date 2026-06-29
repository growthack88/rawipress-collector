"""Rich-only analytics panels: top sources, per category, per hour, success."""
from __future__ import annotations

from rich.console import Group
from rich.text import Text
from textual.widget import Widget

from dashboard.widgets._render import (
    BLUE,
    DIM,
    EMERALD,
    GRAY,
    ORANGE,
    gauge,
    hbar,
)

_CAT_COLOR = {
    "media": BLUE,
    "government": EMERALD,
    "financial": ORANGE,
    "vision2030": "#A855F7",
    "uncategorized": GRAY,
}


class _ChartBase(Widget):
    DEFAULT_CSS = "_ChartBase { height: auto; }"

    def __init__(self, telemetry, **kwargs) -> None:
        super().__init__(**kwargs)
        self._t = telemetry

    def on_mount(self) -> None:
        self.update_view()

    def update_view(self) -> None:
        self.refresh()


class TopSourcesChart(_ChartBase):
    def render(self):
        log = self._t.log()
        top = [s for s in log.top_sources(10) if s.total_fetched > 0]
        if not top:
            return Text("no fetch data yet", style=DIM)
        mx = max(s.total_fetched for s in top)
        rows = [
            hbar(s.name[:14], s.total_fetched, mx, color=EMERALD)
            for s in top
        ]
        return Group(*rows)


class PerCategoryChart(_ChartBase):
    def render(self):
        log = self._t.log()
        data = {k: v for k, v in log.per_category.items() if v > 0}
        if not data:
            return Text("no category data yet", style=DIM)
        mx = max(data.values())
        rows = [
            hbar(cat[:14], val, mx, color=_CAT_COLOR.get(cat, GRAY))
            for cat, val in sorted(data.items(), key=lambda kv: kv[1], reverse=True)
        ]
        return Group(*rows)


class PerHourChart(_ChartBase):
    def render(self):
        log = self._t.log()
        items = sorted(log.per_hour.items())[-12:]
        if not items:
            return Text("no hourly data yet", style=DIM)
        mx = max(v for _, v in items)
        rows = [
            hbar(hour[-5:] + "h", val, mx, color=BLUE)  # show "DD HH"
            for hour, val in items
        ]
        return Group(*rows)


class SuccessGauge(_ChartBase):
    def render(self):
        log = self._t.log()
        total = log.ok_results + log.failed_results
        ok_pct = log.success_rate
        fail_pct = 100 - ok_pct if total else 0
        rows = [
            Text("Collection outcomes", style=f"bold {GRAY}"),
            Text(""),
            Text("Success", style=GRAY),
            gauge(ok_pct, good_high=True),
            Text(""),
            Text("Failure", style=GRAY),
            gauge(fail_pct, good_high=False),
            Text(""),
            Text(f"{log.ok_results} ok · {log.failed_results} failed · {total} total",
                 style=DIM),
        ]
        return Group(*rows)
