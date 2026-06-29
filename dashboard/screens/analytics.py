"""Analytics screen — top sources, categories, hourly throughput, success."""
from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Footer

from dashboard.screens.base import RefreshableScreen
from dashboard.widgets.card import Card
from dashboard.widgets.charts import (
    PerCategoryChart,
    PerHourChart,
    SuccessGauge,
    TopSourcesChart,
)


class AnalyticsScreen(RefreshableScreen):
    def compose(self) -> ComposeResult:
        with Horizontal(id="analytics-body"):
            with Vertical(id="analytics-left"):
                yield Card(
                    TopSourcesChart(self.telemetry),
                    title="TOP SOURCES",
                    subtitle="total items fetched",
                    id="top-card",
                )
                yield Card(
                    PerCategoryChart(self.telemetry),
                    title="BY CATEGORY",
                    id="cat-card",
                )
            with Vertical(id="analytics-right"):
                yield Card(
                    PerHourChart(self.telemetry),
                    title="THROUGHPUT / HOUR",
                    subtitle="fetched per clock hour",
                    id="hour-card",
                )
                yield Card(
                    SuccessGauge(self.telemetry),
                    title="SUCCESS / FAILURE",
                    id="success-card",
                )
        yield Footer()
