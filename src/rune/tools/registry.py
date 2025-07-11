from __future__ import annotations

from collections.abc import Callable
from typing import NamedTuple


class ToolSpec(NamedTuple):
    fn: Callable
    needs_ctx: bool  # True → expects RunContext as 1st arg


# populated when tool modules are imported
REGISTRY: list[ToolSpec] = []


def register_tool(*, needs_ctx: bool = False):
    """
    Decorator for user tools.

    Example:
        @tool()                     # plain callable
        def foo(...): ...

        @tool(needs_ctx=True)       # RunContext in first arg
        def bar(ctx, user_input): ...
    """

    def wrapper(fn: Callable):
        REGISTRY.append(ToolSpec(fn, needs_ctx))
        return fn

    return wrapper
