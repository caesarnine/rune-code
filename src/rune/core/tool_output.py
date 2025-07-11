# src/rune/core/tool_output.py
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ToolOutput(BaseModel):
    """Structured data returned to the LLM on tool success."""

    status: str = Field(
        "success", description="Indicates the tool executed successfully."
    )
    data: Any = Field(..., description="The data payload from the tool.")


class ErrorOutput(BaseModel):
    """Structured data returned to the LLM on tool failure."""

    status: str = Field("error", description="Indicates the tool failed.")
    error_message: str = Field(
        ..., description="A clear, concise description of the error."
    )
