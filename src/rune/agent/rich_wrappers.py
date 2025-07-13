# src/rune/agent/rich_wrappers.py
from __future__ import annotations

import functools
import inspect
from collections.abc import Callable, Coroutine, Sequence
from typing import Any

from pydantic_ai import RunContext, format_as_xml

from rune.adapters.ui import render as ui
from rune.core.tool_output import ErrorOutput, ToolOutput
from rune.core.tool_result import ToolResult


def _infer_param_repr(args: Sequence[Any], kwargs: dict[str, Any]) -> Any:
    """Infers a simple dictionary representation of a function's arguments."""
    if kwargs:
        return kwargs
    if args:
        # Avoid including the RunContext in the displayed parameters
        start_index = 1 if args and isinstance(args[0], RunContext) else 0
        return {f"arg{idx}": val for idx, val in enumerate(args[start_index:], 1)}
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
    4. On success, it prints the tool's final rich renderable and returns a structured
       ToolOutput to the LLM.

    This ensures the agent is ALWAYS informed of tool failures and the user always
    sees the result.
    """
    tool_name = fn.__name__

    def _get_live_manager(args: Sequence[Any]):
        """Safely retrieves the LiveDisplayManager from the RunContext."""
        if args and isinstance(args[0], RunContext):
            return args[0].deps.live_display
        return None

    def handle_result(tool_result: ToolResult, live_manager) -> str:
        """Prints the final renderable and formats the data for the LLM."""
        # For streaming tools, the tool itself updates the live display.
        # The final state is printed here to ensure it's in the scrollback.
        final_renderable = ui._build_tool_result_renderable(tool_name, tool_result)
        if live_manager:
            live_manager.print(final_renderable)
        else:
            ui.console.print(final_renderable)

        success_output = ToolOutput(data=tool_result.data)
        return format_as_xml(success_output, root_tag="tool_result")

    def handle_exception(exc: Exception, live_manager) -> str:
        """Handles any exception, creating a UI error and an LLM error message."""
        error_message = f"Tool '{tool_name}' failed with {type(exc).__name__}: {exc}"
        ui_error_result = ToolResult(status="error", error=error_message, data=None)
        error_frame = ui._build_tool_result_renderable(tool_name, ui_error_result)

        if live_manager:
            live_manager.print(error_frame)
        else:
            ui.console.print(error_frame)

        error_output = ErrorOutput(error_message=error_message)
        return format_as_xml(error_output, root_tag="tool_result")

    if inspect.iscoroutinefunction(fn):

        @functools.wraps(fn)
        async def async_wrapper(*args, **kwargs) -> str:
            live_manager = _get_live_manager(args)
            ui.display_tool_call(tool_name, _infer_param_repr(args, kwargs))
            try:
                tool_result = await fn(*args, **kwargs)
                return handle_result(tool_result, live_manager)
            except Exception as exc:
                return handle_exception(exc, live_manager)

        return async_wrapper
    else:

        @functools.wraps(fn)
        def sync_wrapper(*args, **kwargs) -> str:
            live_manager = _get_live_manager(args)
            ui.display_tool_call(tool_name, _infer_param_repr(args, kwargs))
            try:
                tool_result = fn(*args, **kwargs)
                return handle_result(tool_result, live_manager)
            except Exception as exc:
                return handle_exception(exc, live_manager)

        return sync_wrapper
