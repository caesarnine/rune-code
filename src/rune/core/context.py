# src/rune/core/context.py
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rune.core.models import Todo


@dataclass
class SessionContext:
    """Holds all runtime state for a single chat session."""

    # The agent's current working directory. Solves the state bug in `run_command`.
    # Defaults to the directory where Rune was launched.
    current_working_dir: Path = field(default_factory=Path.cwd)

    # The session-specific to-do list. Replaces the global `_TODOS` variable.
    todos: dict[str, Todo] = field(default_factory=dict)
