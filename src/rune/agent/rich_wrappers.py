# src/rune/agent/rich_wrappers.py
from __future__ import annotations

import functools
import inspect
from collections.abc import Callable, Coroutine, Sequence
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


def rich_tool(
    fn: Callable[..., ToolResult] | Callable[..., Coroutine[Any, Any, ToolResult]],
):
    """
    Decorator that handles the complete tool lifecycle for both sync and async tools:
    1. Renders the tool call UI.
    2. Executes the tool (sync or async).
    3. Catches ANY exception, rendering a UI error and returning a structured
       ErrorOutput to the LLM.
    4. On success, renders the tool's UI result and returns a structured
       ToolOutput to the LLM.

    This ensures the agent is ALWAYS informed of tool failures.
    """
    tool_name = fn.__name__

    def handle_result(tool_result: ToolResult) -> str:
        ui.display_tool_result(tool_name, tool_result)
        success_output = ToolOutput(data=tool_result.data)
        return format_as_xml(success_output, root_tag="tool_result")

    def handle_exception(exc: Exception) -> str:
        error_message = f"Tool '{tool_name}' failed with {type(exc).__name__}: {exc}"
        ui_error_result = ToolResult(status="error", error=error_message, data=None)
        ui.display_tool_result(tool_name, ui_error_result)
        error_output = ErrorOutput(error_message=error_message)
        return format_as_xml(error_output, root_tag="tool_result")

    if inspect.iscoroutinefunction(fn):

        @functools.wraps(fn)
        async def async_wrapper(*args, **kwargs) -> str:
            ui.display_tool_call(tool_name, _infer_param_repr(args, kwargs))
            try:
                tool_result = await fn(*args, **kwargs)
                return handle_result(tool_result)
            except Exception as exc:
                return handle_exception(exc)

        return async_wrapper
    else:

        @functools.wraps(fn)
        def sync_wrapper(*args, **kwargs) -> str:
            ui.display_tool_call(tool_name, _infer_param_repr(args, kwargs))
            try:
                tool_result = fn(*args, **kwargs)
                return handle_result(tool_result)
            except Exception as exc:
                return handle_exception(exc)

        return sync_wrapper
