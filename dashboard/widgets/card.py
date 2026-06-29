"""A bordered, titled container — the panel chrome used across screens."""
from __future__ import annotations

from textual.containers import Vertical


class Card(Vertical):
    """A titled panel. Wrap content widgets in a Card for the boxed look."""

    def __init__(self, *children, title: str = "", subtitle: str = "", **kwargs) -> None:
        super().__init__(*children, **kwargs)
        self._title = title
        self._subtitle = subtitle

    def on_mount(self) -> None:
        if self._title:
            self.border_title = self._title
        if self._subtitle:
            self.border_subtitle = self._subtitle
