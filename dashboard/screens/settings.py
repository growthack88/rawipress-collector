"""Settings screen — node configuration, paths, and ingest readiness."""
from __future__ import annotations

from rich.console import Group
from rich.table import Table
from rich.text import Text
from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Footer

from dashboard.screens.base import RefreshableScreen
from dashboard.widgets._render import BLUE, DIM, EMERALD, GRAY, ORANGE, RED
from dashboard.widgets.card import Card
from dashboard.telemetry import paths


def _row(table: Table, key: str, value: Text) -> None:
    table.add_row(Text(key, style=GRAY), value)


class SettingsPanel(Widget):
    DEFAULT_CSS = "SettingsPanel { height: auto; padding: 0 1; }"

    def __init__(self, telemetry, **kwargs) -> None:
        super().__init__(**kwargs)
        self._t = telemetry

    def on_mount(self) -> None:
        self.update_view()

    def update_view(self) -> None:
        self.refresh()

    def render(self):
        m = self._t.metrics()
        reg = self._t.registry()

        env = Table.grid(padding=(0, 2))
        env.add_column(width=18)
        env.add_column(ratio=1)
        ready = m.ingest_ready
        _row(env, "Ingest", Text("CONFIGURED" if ready else "NOT CONFIGURED",
                                 style=EMERALD if ready else ORANGE))
        _row(env, ".env file", _exists(paths.ENV_FILE))
        cache = m.sent_cache
        _row(env, "Sent cache", Text(
            f"ON · {cache.count} urls · {cache.unique_domains} domains" if cache.enabled
            else "OFF (RAWI_SENT_CACHE=0)",
            style=EMERALD if cache.enabled else DIM))
        _row(env, "Host uptime", Text(m.host_uptime, style=BLUE))

        reg_t = Table.grid(padding=(0, 2))
        reg_t.add_column(width=18)
        reg_t.add_column(ratio=1)
        _row(reg_t, "Sources", Text(f"{reg.total}  ({reg.news} news · {reg.social} social)", style=EMERALD))
        _row(reg_t, "Enabled", Text(str(reg.enabled), style=EMERALD))
        _row(reg_t, "Verified", Text(str(reg.verified),
                                     style=EMERALD if reg.verified else ORANGE))
        _row(reg_t, "Wired to cloud", Text(str(reg.wired),
                                           style=EMERALD if reg.wired else ORANGE))
        _row(reg_t, "Methods", Text(", ".join(f"{k}:{v}" for k, v in reg.by_method.items()), style=GRAY))

        path_t = Table.grid(padding=(0, 2))
        path_t.add_column(width=18)
        path_t.add_column(ratio=1)
        _row(path_t, "Root", Text(str(paths.ROOT), style=GRAY))
        _row(path_t, "Sources file", _exists(paths.SOURCES_FILE))
        _row(path_t, "Log file", Text(f"{paths.LOG_FILE}  ({m.log_size})", style=GRAY))
        _row(path_t, "Data dir", _exists(paths.DATA_DIR))

        return Group(
            Text("▎ INGEST & RUNTIME", style=f"bold {EMERALD}"), Text(""), env, Text(""),
            Text("▎ REGISTRY", style=f"bold {BLUE}"), Text(""), reg_t, Text(""),
            Text("▎ PATHS", style=f"bold {ORANGE}"), Text(""), path_t,
        )


def _exists(p) -> Text:
    return Text(f"✓ {p}", style=EMERALD) if p.exists() else Text(f"✗ {p} (missing)", style=RED)


class SettingsScreen(RefreshableScreen):
    def compose(self) -> ComposeResult:
        yield Card(
            SettingsPanel(self.telemetry),
            title="SETTINGS · NODE CONFIGURATION",
            subtitle="read-only",
            id="settings-card",
        )
        yield Footer()
