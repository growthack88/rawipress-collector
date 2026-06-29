"""Operations-center masthead: ASCII logo, system status strip, live clock."""
from __future__ import annotations

from datetime import datetime

from rich.console import Group
from rich.text import Text
from textual.widget import Widget

from dashboard.widgets._render import BLUE, DIM, DOT, EMERALD, FG, GRAY, ORANGE, RED

_LOGO = r"""
██████╗  █████╗ ██╗    ██╗██╗
██╔══██╗██╔══██╗██║    ██║██║
██████╔╝███████║██║ █╗ ██║██║
██╔══██╗██╔══██║██║███╗██║██║
██║  ██║██║  ██║╚███╔███╔╝██║
╚═╝  ╚═╝╚═╝  ╚═╝ ╚══╝╚══╝ ╚═╝"""


class LogoHeader(Widget):
    """Static logo + a once-per-second status strip and clock."""

    DEFAULT_CSS = """
    LogoHeader {
        height: auto;
        padding: 0 1;
    }
    """

    def __init__(self, telemetry, **kwargs) -> None:
        super().__init__(**kwargs)
        self._t = telemetry

    def on_mount(self) -> None:
        self.update_view()

    def update_view(self) -> None:
        self.refresh(layout=True)

    def render(self):
        logo = Text(_LOGO, style=f"bold {EMERALD}")
        title = Text()
        title.append("RAWI PRESS", style=f"bold {FG}")
        title.append("  ·  ", style=DIM)
        title.append("SAUDI INTELLIGENCE OPERATIONS CENTER", style=f"bold {BLUE}")

        try:
            log = self._t.log()
            metrics = self._t.metrics()
            ingest = metrics.ingest_ready
            collecting = self._fresh(log.last_run_ts)
        except Exception:
            ingest, collecting = False, False
            log = None

        strip = Text()
        self._chip(strip, "ONLINE", EMERALD)
        self._chip(strip, "INGEST READY" if ingest else "INGEST UNCONFIGURED",
                   EMERALD if ingest else ORANGE)
        self._chip(strip, "COLLECTING" if collecting else "IDLE",
                   EMERALD if collecting else BLUE)
        self._chip(strip, "MONITORING", BLUE)
        if log is not None:
            self._chip(strip, f"{log.errors_today} ERR TODAY",
                       RED if log.errors_today else DIM)

        clock = Text(datetime.now().strftime("%a %d %b %Y  %H:%M:%S"), style=f"bold {GRAY}")

        return Group(logo, title, Text(""), strip, clock)

    @staticmethod
    def _chip(text: Text, label: str, color: str) -> None:
        text.append(f"{DOT} ", style=color)
        text.append(f"{label}   ", style=f"bold {color}")

    @staticmethod
    def _fresh(ts, within_seconds: int = 1800) -> bool:
        if ts is None:
            return False
        return (datetime.now() - ts).total_seconds() < within_seconds
