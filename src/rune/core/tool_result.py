from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from rich.console import RenderableType


@dataclass
class ToolResult:
    """Container that carries data for the LLM and an optional Rich renderable for humans."""

    data: Any
    renderable: RenderableType | None = None
    status: str = "success"  # "success" | "error"
    error: str | None = None
