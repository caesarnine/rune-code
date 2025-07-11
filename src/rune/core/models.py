# src/rune/core/models.py
import dataclasses
from typing import Literal


@dataclasses.dataclass
class Todo:
    """Represents a single task in the to-do list."""

    id: str
    title: str
    status: Literal["pending", "in_progress", "completed", "cancelled"]
    priority: Literal["low", "medium", "high"]
    note: str | None = None
