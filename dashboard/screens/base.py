"""Base screen with tiered 1 Hz auto-refresh.

Widgets may declare ``REFRESH_EVERY = n`` (in ticks) to refresh less often than
every second — tables use this so a rebuild doesn't fight the user's cursor.
A widget refreshes by exposing an ``update_view()`` method.
"""
from __future__ import annotations

from textual.screen import Screen
from textual.widget import Widget


class RefreshableScreen(Screen):
    """Drives a once-per-second refresh of all telemetry widgets on the screen."""

    REFRESH_INTERVAL = 1.0

    def __init__(self, telemetry, **kwargs) -> None:
        super().__init__(**kwargs)
        self.telemetry = telemetry
        self._tick = 0

    def on_mount(self) -> None:
        self.set_interval(self.REFRESH_INTERVAL, self._on_tick)
        self._on_tick()

    def _on_tick(self) -> None:
        self._tick += 1
        for widget in self.walk_children(Widget):
            fn = getattr(widget, "update_view", None)
            if fn is None:
                continue
            every = getattr(widget, "REFRESH_EVERY", 1)
            if every and self._tick % every == 0:
                try:
                    fn()
                except Exception:
                    pass
