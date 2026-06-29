"""Home dashboard — masthead, live stats, activity feed, source health."""
from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Footer

from dashboard.screens.base import RefreshableScreen
from dashboard.widgets.activity import ActivityFeed
from dashboard.widgets.card import Card
from dashboard.widgets.charts import SuccessGauge
from dashboard.widgets.header import LogoHeader
from dashboard.widgets.health import SourceHealth
from dashboard.widgets.stats import StatsGrid


class DashboardScreen(RefreshableScreen):
    def compose(self) -> ComposeResult:
        yield LogoHeader(self.telemetry, id="masthead")
        with Horizontal(id="dash-body"):
            with Vertical(id="dash-left"):
                yield Card(
                    StatsGrid(self.telemetry, columns=4),
                    title="LIVE STATISTICS",
                    subtitle="node · registry · host",
                    id="stats-card",
                )
                yield Card(
                    SuccessGauge(self.telemetry),
                    title="COLLECTION OUTCOMES",
                    id="outcomes-card",
                )
            with Vertical(id="dash-right"):
                yield Card(
                    ActivityFeed(self.telemetry, limit=16),
                    title="LIVE ACTIVITY",
                    subtitle="newest first",
                    id="activity-card",
                )
                yield Card(
                    SourceHealth(self.telemetry, limit=12),
                    title="SOURCE HEALTH",
                    id="health-card",
                )
        yield Footer()
