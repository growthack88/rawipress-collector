"""Sources screen — the full registry with reconciled health, filterable."""
from __future__ import annotations

from textual.app import ComposeResult
from textual.widgets import Footer

from dashboard.screens.base import RefreshableScreen
from dashboard.widgets.card import Card
from dashboard.widgets.source_table import SourceTable


class SourcesScreen(RefreshableScreen):
    def compose(self) -> ComposeResult:
        table = SourceTable(self.telemetry, id="sources-table")
        table.REFRESH_EVERY = 5  # rebuild every 5s, not every tick
        yield Card(
            table,
            title="SOURCE REGISTRY",
            subtitle="config/sources.json · ✓ enabled/verified/wired · live status from log",
            id="sources-card",
        )
        yield Footer()

    def apply_filter(self, query: str) -> None:
        self.query_one(SourceTable).set_filter(query)
