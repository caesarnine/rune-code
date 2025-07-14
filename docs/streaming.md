# Streaming UI

The streaming UI is built around the `LiveDisplayManager` class, which manages a single Rich Live display for an agent turn. The `LiveDisplayManager` is a context manager that can be used to ensure that the live display is always correctly started and stopped, even in the case of exceptions or interruptions.

## `LiveDisplayManager`

The `LiveDisplayManager` can be used as a synchronous or asynchronous context manager. When used as a context manager, it will automatically start the live display when the context is entered and stop it when the context is exited.

### `live.update`

The `live.update` method can be used to update the content of the live display. This method takes a single argument, which is the renderable to be displayed.

### `stream_to_live`

The `stream_to_live` helper is an asynchronous context manager that can be used to periodically refresh a `LiveDisplayManager` instance. This makes it easier to implement streaming UI updates in other parts of the application.

## Example

Here is an example of how to create a new tool that uses the streaming UI:

```python
import asyncio
from rune.adapters.ui.live_display import LiveDisplayManager
from rune.tools.registry import register_tool
from rune.core.tool_result import ToolResult
from rune.utils.stream import stream_to_live
from rich.text import Text

@register_tool(needs_ctx=True)
async def my_streaming_tool(ctx, ...):
    live_manager = ctx.deps.live_display
    is_dirty = False
    output = ""

    def set_dirty():
        nonlocal is_dirty
        is_dirty = True

    def build_frame():
        nonlocal is_dirty
        is_dirty = False
        return Text(output)

    async def my_long_running_task():
        nonlocal output
        for i in range(10):
            await asyncio.sleep(0.1)
            output += f"Hello, world! {i}\n"
            set_dirty()

    async with stream_to_live(live_manager, build_frame, lambda: is_dirty):
        await my_long_running_task()

    return ToolResult(data=...)
```
