# src/rune/agent/rich_wrappers.py
from __future__ import annotations

import functools
from collections.abc import Callable, Sequence
from typing import Any

from pydantic_ai import format_as_xml

from rune.adapters.ui import render as ui
from rune.core.tool_output import ErrorOutput, ToolOutput
from rune.core.tool_result import ToolResult


def _infer_param_repr(args: Sequence[Any], kwargs: dict[str, Any]) -> Any:
    if kwargs:
        return kwargs
    if args:
        return {f"arg{idx}": val for idx, val in enumerate(args)}
    return {}


def rich_tool(fn: Callable[..., ToolResult]):
    """
    Decorator that handles the complete tool lifecycle:
    1. Renders the tool call UI.
    2. Executes the tool.
    3. Catches ANY exception, rendering a UI error and returning a structured
       ErrorOutput to the LLM.
    4. On success, renders the tool's UI result and returns a structured
       ToolOutput to the LLM.

    This ensures the agent is ALWAYS informed of tool failures.
    """
    tool_name = fn.__name__

    @functools.wraps(fn)
    def wrapper(*args, **kwargs) -> str:
        ui.display_tool_call(tool_name, _infer_param_repr(args, kwargs))

        try:
            # --- Success Path ---
            # All tools are now expected to return a ToolResult on success.
            tool_result = fn(*args, **kwargs)

            ui.display_tool_result(tool_name, tool_result)

            # Create the clean ToolOutput for the LLM.
            success_output = ToolOutput(data=tool_result.data)
            return format_as_xml(success_output, root_tag="tool_result")

        except Exception as exc:
            # --- Unified Failure Path ---
            # Catch ANY exception from the tool.
            error_message = (
                f"Tool '{tool_name}' failed with {type(exc).__name__}: {exc}"
            )

            # Create a temporary ToolResult for consistent UI rendering.
            ui_error_result = ToolResult(status="error", error=error_message, data=None)
            ui.display_tool_result(tool_name, ui_error_result)

            # Create the clean ErrorOutput for the LLM.
            error_output = ErrorOutput(error_message=error_message)
            return format_as_xml(error_output, root_tag="tool_result")

    return wrapper
