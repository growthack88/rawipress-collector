"""Shared rendering helpers: palette, status glyphs, stat tiles, bar charts."""
from __future__ import annotations

from rich.align import Align
from rich.console import Group, RenderableType
from rich.table import Table
from rich.text import Text

# ── palette (matches the registered Textual theme) ─────────────────────────
EMERALD = "#22C55E"
BLUE = "#0EA5E9"
ORANGE = "#F59E0B"
RED = "#EF4444"
GRAY = "#A1A1AA"
FG = "#E4E4E7"
DIM = "#52525B"

STATUS_STYLE = {
    "online": EMERALD,
    "warning": ORANGE,
    "error": RED,
    "offline": DIM,
    "idle": BLUE,
}
STATUS_LABEL = {
    "online": "ONLINE",
    "warning": "WARNING",
    "error": "ERROR",
    "offline": "OFFLINE",
    "idle": "IDLE",
}
LEVEL_STYLE = {"info": EMERALD, "warning": ORANGE, "error": RED}

DOT = "●"


def status_text(status: str) -> Text:
    style = STATUS_STYLE.get(status, GRAY)
    return Text(f"{DOT} {STATUS_LABEL.get(status, status.upper())}", style=style)


def stat_tile(label: str, value: str, *, unit: str = "", color: str = EMERALD) -> Table:
    """A compact label-over-value tile."""
    t = Table.grid(padding=0)
    t.add_column(justify="left")
    t.add_row(Text(label.upper(), style=f"dim {GRAY}"))
    val = Text(str(value), style=f"bold {color}")
    if unit:
        val.append(f" {unit}", style=f"dim {GRAY}")
    t.add_row(val)
    return t


def stat_grid(tiles: list[tuple[str, str, str]], columns: int = 4) -> Table:
    """Lay out (label, value, color) tiles in a column grid.

    ``value`` may contain a trailing ' <unit>' which is dimmed automatically by
    the caller passing it pre-joined; here we keep it simple.
    """
    grid = Table.grid(expand=True, padding=(0, 1))
    for _ in range(columns):
        grid.add_column(ratio=1)
    row: list[RenderableType] = []
    for label, value, color in tiles:
        row.append(stat_tile(label, value, color=color))
        if len(row) == columns:
            grid.add_row(*row)
            row = []
    if row:
        while len(row) < columns:
            row.append("")
        grid.add_row(*row)
    return grid


def hbar(label: str, value: float, maximum: float, *, width: int = 22,
         color: str = EMERALD, suffix: str = "") -> Text:
    """A horizontal bar: ``label  ███████░░░  value``."""
    maximum = max(maximum, 1)
    filled = int(round((value / maximum) * width))
    filled = max(0, min(width, filled))
    bar = Text()
    bar.append(f"{label:<14}", style=GRAY)
    bar.append("█" * filled, style=color)
    bar.append("░" * (width - filled), style=DIM)
    bar.append(f"  {suffix or value:g}" if not suffix else f"  {suffix}", style=f"bold {FG}")
    return bar


def gauge(pct: float, *, width: int = 24, good_high: bool = True) -> Text:
    filled = int(round(pct / 100 * width))
    if good_high:
        color = EMERALD if pct >= 80 else ORANGE if pct >= 50 else RED
    else:
        color = RED if pct >= 80 else ORANGE if pct >= 50 else EMERALD
    g = Text()
    g.append("█" * filled, style=color)
    g.append("░" * (width - filled), style=DIM)
    g.append(f"  {pct:.0f}%", style=f"bold {color}")
    return g


def titled(title: str, body: RenderableType, accent: str = EMERALD) -> Group:
    head = Text(f"▎{title}", style=f"bold {accent}")
    return Group(head, Text(""), body)


def centered(renderable: RenderableType) -> Align:
    return Align.center(renderable, vertical="middle")
