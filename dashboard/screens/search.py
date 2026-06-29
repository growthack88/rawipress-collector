"""Modal search overlay — filter sources / captured articles by substring."""
from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, Label


class SearchScreen(ModalScreen[str]):
    """Returns the entered query (or '' if cancelled) to the caller."""

    BINDINGS = [("escape", "cancel", "Cancel")]

    def compose(self) -> ComposeResult:
        with Vertical(id="search-box"):
            yield Label("⌕  SEARCH  ·  sources & captured articles", id="search-title")
            yield Input(
                placeholder="Aramco · Vision 2030 · NEOM · energy · spa …",
                id="search-input",
            )
            yield Label("enter to apply · esc to cancel", id="search-hint")

    def on_mount(self) -> None:
        self.query_one(Input).focus()

    @on(Input.Submitted)
    def _submit(self, event: Input.Submitted) -> None:
        self.dismiss(event.value.strip())

    def action_cancel(self) -> None:
        self.dismiss("")
