from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator, Callable
from contextlib import asynccontextmanager

from rich.console import RenderableType

from rune.adapters.ui.live_display import LiveDisplayManager


@asynccontextmanager
async def stream_to_live(
    live: LiveDisplayManager,
    build_renderable: Callable[[], RenderableType],
    flag_is_dirty: Callable[[], bool],
    *,
    interval: float = 0.08,
) -> AsyncGenerator[None, None]:
    """
    Periodically calls *build_renderable* and pushes it to *live*
    whenever *flag_is_dirty()* is True.

    Usage:
        dirty = False
        def mark(): nonlocal dirty; dirty = True

        async with stream_to_live(...):
            mark() # inside your reader tasks
    """
    stop_evt = asyncio.Event()

    async def _runner(stop: asyncio.Event):
        while not stop.is_set():
            if flag_is_dirty():
                live.update(build_renderable())
            try:
                await asyncio.wait_for(asyncio.sleep(interval), timeout=interval + 0.5)
            except asyncio.TimeoutError:
                # This can happen if the system is under heavy load.
                # We just continue to the next iteration.
                pass

    task = asyncio.create_task(_runner(stop_evt))
    try:
        yield
    finally:
        stop_evt.set()
        await task
