# src/rune/adapters/ui/live_display.py (New File)
from __future__ import annotations
from typing import Any

from rich.console import RenderableType
from rich.live import Live
from rich.spinner import Spinner

from .console import console


class LiveDisplayManager:
    """Manages a single Rich Live display for an agent turn."""

    def __init__(self):
        self._live: Live | None = None
        self._current_renderable: RenderableType | None = None

    def start(self, initial_renderable: RenderableType | None = None) -> None:
        """Starts the live display."""
        if initial_renderable is None:
            initial_renderable = Spinner("dots", text=" Thinking...")

        self._current_renderable = initial_renderable
        self._live = Live(self._current_renderable, console=console, transient=True)
        self._live.start()

    def update(self, renderable: RenderableType) -> None:
        """Updates the content of the live display."""
        if self._live:
            self._current_renderable = renderable
            self._live.update(self._current_renderable)

    def print(self, message: Any) -> None:
        """Prints a message *above* the live display, leaving it in the scrollback."""
        if self._live:
            self._live.console.print(message)

    def stop(self) -> None:
        """Stops and cleans up the live display."""
        if self._live:
            self._live.stop()
            self._live = None
