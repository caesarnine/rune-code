## 0  Scaffolding & branch

```bash
git checkout -b feat/stream-ui-refactor
```

---

## 1  UI primitives: **BarFrame**

| Why | All three render paths (prose, tool-call, tool-result) hand-roll the same “gutter │ indent” logic. |
| --- | -------------------------------------------------------------------------------------------------- |

1. **Create** `src/rune/adapters/ui/components.py`

   ```python
   # new file
   from __future__ import annotations
   from rich.console import RenderableType, Group
   from rich.text import Text

   def bar_frame(
       body: RenderableType,
       *,
       glyph: str,
       bar_style: str,
       indent: str = "  ",
   ) -> Group:
       """
       Wrap *body* with a coloured gutter and indent so callers
       never touch bar-rendering again.
       """
       gutter = Text(f"[{bar_style}]{glyph}[/] ")
       spacer = Text(indent)
       # Render *body* into a table grid the same way _build_tool_result_renderable does,
       # but in one reusable place.
       ...
   ```

   > (Fill in with a trimmed version of the existing grid logic.)

2. **Refactor** `src/rune/adapters/ui/render.py`

   * import `bar_frame`
   * Replace internal bar logic in:

     * `_render_with_bar`
     * `display_tool_call`
     * `_build_tool_result_renderable`

   Keep the existing public signatures unchanged.

---

## 2  `LiveDisplayManager` -> context manager

**File:** `src/rune/adapters/ui/live_display.py`

```python
class LiveDisplayManager:
    def __enter__(self):        # sync context for tooling
        self.start()
        return self
    def __exit__(self, exc_type, exc, tb):
        self.stop()

    async def __aenter__(self): # async context for run_agent_turn
        self.start()
        return self
    async def __aexit__(self, exc_type, exc, tb):
        self.stop()
```

*No behaviour change yet, only ergonomics.*

---

## 3  Use the context manager in the chat loop

**File:** `src/rune/cli/chat.py`

```diff
- live_display = LiveDisplayManager()
- session_ctx.live_display = live_display
- live_display.start()
+ async with LiveDisplayManager() as live_display:
+     session_ctx.live_display = live_display
+     ...
+     # the whole agent.iter loop lives here
+ session_ctx.live_display = None
```

This guarantees cleanup even on Ctrl-C.

---

## 4  Generic streaming helper

**New file:** `src/rune/utils/stream.py`

```python
from __future__ import annotations
import asyncio
from typing import Awaitable, Callable
from rune.adapters.ui.live_display import LiveDisplayManager

async def stream_to_live(
    live: LiveDisplayManager,
    build_renderable: Callable[[], "RenderableType"],
    flag_is_dirty: Callable[[], bool],
    *,
    interval: float = 0.08,
) -> Awaitable[None]:
    """
    Periodically calls *build_renderable* and pushes it to *live*
    whenever *flag_is_dirty()* is True.
    Usage:
        dirty = False
        def mark(): nonlocal dirty; dirty = True
        async with stream_to_live(...):
            mark() inside your reader tasks
    """
    async def _runner(stop: asyncio.Event):
        while not stop.is_set():
            if flag_is_dirty():
                live.update(build_renderable())
            await asyncio.sleep(interval)

    stop_evt = asyncio.Event()
    task = asyncio.create_task(_runner(stop_evt))
    try:
        yield
    finally:
        stop_evt.set()
        await task
```

*Expose this function in `__all__` for reuse.*

---

## 5  Refactor **run\_command** to use the helper

**File:** `src/rune/tools/run_command.py`

1. Remove the bespoke `render_loop()`.
2. Hold `is_dirty` and `build_frame` closures.
3. Wrap reader coroutines:

```python
async with stream_to_live(live_manager, build_frame, lambda: is_dirty):
    await asyncio.wait_for(reader_tasks, timeout)
```

The rest of the logic (exit-code handling, final `ToolResult`) stays unchanged.

---

## 6  True streaming for **run\_python**

**File:** `src/rune/tools/run_python.py`

1. Add optional `live_manager` param (detect via `SessionContext` similarly to `run_command`).
2. Re-organise message loop:

```python
stdout_lines: list[str] = []
is_dirty = False

def build_frame():
    return _create_renderable(code, [{"type": "stream", ...}, *outputs])

async with stream_to_live(live_manager, build_frame, lambda: is_dirty):
    while True:
        msg = await asyncio.to_thread(client.get_iopub_msg, timeout=1)
        if msg["parent_header"].get("msg_id") != msg_id:
            continue
        # append to outputs, set is_dirty = True
```

3. Return the same final `ToolResult` as today.

---

## 7  Spinner text deduplication

*Add a constant* `SPINNER_TEXT = "Thinking..."` to `glyphs.py`
Replace literal string in `chat.run_agent_turn` and `render.prose()`.

---

## 8  Tests

### 8.1 `tests/tools/test_stream_run_command.py`

```python
import asyncio
from rune.adapters.ui.live_display import LiveDisplayManager
from rune.tools.run_command import run_command
from pydantic_ai import RunContext
from rune.core.context import SessionContext

async def test_streaming_updates(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    session = SessionContext()
    async with LiveDisplayManager() as live:
        session.live_display = live
        await run_command(
            RunContext(model="mock", deps=session, prompt=""),
            "bash -c 'echo one; sleep 0.05; echo two'",
            timeout=2,
        )
        # No assertions on console; the test passes if no exception is raised
```

### 8.2 BarFrame snapshot

Add a Rich snapshot (pytest-recording) for `bar_frame` to ensure visual regressions.

---

## 9  Docs

### 9.1 `docs/streaming.md`

* Outline contract (`live.update`, context manager, stream\_to\_live).
* Give “Hello World” example for a new tool.

### 9.2 README

* Under **Architecture overview** add a bullet “Streaming tools ↔ `LiveDisplayManager`”.

---

## 10  Housekeeping

* Run `ruff format .` & `ruff check .`
* Update `__init__.py` exports if needed.
* Commit:

```bash
git add -A
git commit -m "Streaming UI refactor: BarFrame, context-managed LiveDisplay, stream_to_live helper, tool updates, tests, docs"
```

---

## 11  Future (post-merge) backlog

* Per-tool nested Live instances (flag on `rich_tool`).
* Auto-type-check for tool return types in a pytest plug-in.
* Bring colour & glyph palette into a single theme JSON for easy theming.
