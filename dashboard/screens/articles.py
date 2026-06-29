"""Articles screen — live capture of REAL headlines from the sources.

There is no local article database (the node is push-only), so "articles" here
are produced on demand by a live capture: ``app.py dry-run`` fetches from the
live sources and returns the mapped items, which we list and inspect. Press R
to run a capture.
"""
from __future__ import annotations

from rich.console import Group
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widget import Widget
from textual.widgets import DataTable, Footer, Static

from dashboard.screens.base import RefreshableScreen
from dashboard.widgets._render import BLUE, DIM, EMERALD, GRAY, ORANGE
from dashboard.widgets.card import Card
from dashboard.widgets.feed import CaptureFeed


class CaptureStatus(Static):
    """One-line status describing the current/last capture."""

    DEFAULT_CSS = "CaptureStatus { height: 1; padding: 0 1; }"

    def __init__(self, telemetry, **kwargs) -> None:
        super().__init__(**kwargs)
        self._t = telemetry

    def update_view(self) -> None:
        running = getattr(self._t, "capture_running", False)
        last = getattr(self._t, "last_capture", None)
        if running:
            tgt = getattr(self._t, "capture_target", "all")
            self.update(Text(f"◌ capturing {tgt} … live fetch, may take ~30s",
                             style=f"bold {ORANGE}"))
        elif last is None:
            self.update(Text("press R to run a live capture (real fetch, nothing is stored)",
                             style=DIM))
        elif last.ok:
            self.update(Text(
                f"● captured {len(last.articles)} items from {last.target} "
                f"at {last.ran_at.strftime('%H:%M:%S')}",
                style=f"bold {EMERALD}"))
        else:
            self.update(Text(f"✗ capture failed: {last.error}", style=f"bold {ORANGE}"))


class ArticleDetail(Widget):
    """Detail panel for the highlighted captured article."""

    DEFAULT_CSS = "ArticleDetail { height: 1fr; padding: 0 1; }"

    def __init__(self, telemetry, **kwargs) -> None:
        super().__init__(**kwargs)
        self._t = telemetry
        self.article = None

    def show(self, article) -> None:
        self.article = article
        self.refresh()

    def update_view(self) -> None:
        self.refresh()

    def render(self):
        a = self.article
        if a is None:
            return Text("select an article to inspect", style=DIM)
        body = a.body or "(no body extracted)"
        excerpt = body[:1200] + ("…" if len(body) > 1200 else "")
        return Group(
            Text(a.title or "(untitled)", style=f"bold {EMERALD}"),
            Text(""),
            Text(f"source   {a.source}", style=GRAY),
            Text(f"posted   {a.posted_at or '—'}", style=GRAY),
            Text(f"chars    {len(a.body)}", style=GRAY),
            Text(f"url      {a.url}", style=BLUE, overflow="fold"),
            Text(""),
            Text("─" * 40, style=DIM),
            Text(""),
            Text(excerpt, style=GRAY, overflow="fold"),
        )


class ArticlesScreen(RefreshableScreen):
    _auto_started = False

    def compose(self) -> ComposeResult:
        with Card(title="LIVE CAPTURE",
                  subtitle="real headlines via app.py dry-run · press R to capture",
                  id="articles-card"):
            yield CaptureStatus(self.telemetry, id="capture-status")
            with Horizontal(id="articles-body"):
                feed = CaptureFeed(self.telemetry, id="capture-feed")
                feed.REFRESH_EVERY = 3
                yield feed
                yield ArticleDetail(self.telemetry, id="article-detail")
        yield Footer()

    def on_mount(self) -> None:
        super().on_mount()
        if not ArticlesScreen._auto_started and not self.telemetry.captured:
            ArticlesScreen._auto_started = True
            self.app.run_capture(self._default_source())

    def _default_source(self) -> str | None:
        news = [s for s in self.telemetry.sources()
                if s.kind == "news" and s.enabled and s.verified]
        news = news or [s for s in self.telemetry.sources()
                        if s.kind == "news" and s.enabled]
        news.sort(key=lambda s: s.priority)
        return news[0].name if news else None

    def apply_filter(self, query: str) -> None:
        self.query_one(CaptureFeed).set_filter(query)

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        feed = self.query_one(CaptureFeed)
        self.query_one(ArticleDetail).show(feed.current_article())
