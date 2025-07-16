# src/rune/core/models.py
from typing import Literal

from pydantic import BaseModel


class Todo(BaseModel):
    """Represents a single task in the to-do list."""

    id: str
    title: str
    status: Literal["pending", "in_progress", "completed", "cancelled"]
    priority: Literal["low", "medium", "high"]
    note: str | None = None
