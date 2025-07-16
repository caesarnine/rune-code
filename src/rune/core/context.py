# src/rune/core/context.py
from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field, PrivateAttr

from rune.adapters.ui.live_display import LiveDisplayManager
from rune.core.models import Todo


class SessionContext(BaseModel):
    """Holds all runtime state for a single chat session."""

    current_working_dir: Path = Field(default_factory=Path.cwd)
    todos: dict[str, Todo] = Field(default_factory=dict)

    # The `live_display` is a transient object that should not be persisted.
    _live_display: LiveDisplayManager | None = PrivateAttr(default=None)

    @property
    def live_display(self) -> LiveDisplayManager | None:
        return self._live_display

    @live_display.setter
    def live_display(self, value: LiveDisplayManager | None) -> None:
        self._live_display = value
