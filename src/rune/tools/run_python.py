from __future__ import annotations

import asyncio
from queue import Empty
from typing import Any

from jupyter_client.manager import KernelManager
from pydantic_ai import RunContext
from rich.console import Group
from rich.text import Text

from rune.core.context import RuneDependencies, SessionContext
from rune.core.tool_result import ToolResult

_kernel_manager = None
_kernel_client = None


def _get_kernel_client():
    global _kernel_manager, _kernel_client
    if _kernel_manager is None:
        _kernel_manager = KernelManager()
        _kernel_manager.start_kernel()
    if _kernel_client is None:
        _kernel_client = _kernel_manager.client()
        _kernel_client.start_channels()
    return _kernel_client


def _create_renderable(code: str, outputs: list[dict[str, Any]]) -> Group:
    has_error = any(o["type"] == "error" for o in outputs)

    if has_error:
        glyph, message, style = "!", "Python Error", "red"
    else:
        glyph, message, style = ">", "Python Execution", "green"

    header_content = f"{glyph} {message}"
    header_text = f"┌─ {header_content} "
    header = Text(header_text + "─" * (70 - len(header_text)), style=f"bold {style}")

    body = [header]
    body.append(Text(f"│ >>> {code}", style="bold cyan"))

    if outputs:
        body.append(Text("│"))

    for output in outputs:
        if output["type"] == "stream":
            text = output.get("text", "")
            for line in text.strip().splitlines():
                line_style = "yellow" if output.get("name") == "stderr" else "default"
                body.append(Text(f"│ {line}", style=line_style))
        elif output["type"] == "execute_result":
            data = output.get("data", {})
            for line in data.get("text/plain", "").strip().splitlines():
                body.append(Text(f"│ {line}"))
        elif output["type"] == "display_data":
            data = output.get("data", {})
            if "image/png" in data:
                body.append(
                    Text(
                        f"│ [Image (PNG, {len(data['image/png'])} bytes)]",
                        style="italic",
                    )
                )
            elif "text/plain" in data:
                for line in data.get("text/plain", "").strip().splitlines():
                    body.append(Text(f"│ {line}", style="dim"))
        elif output["type"] == "error":
            traceback = output.get("traceback", [])
            for line in traceback:
                body.append(Text(f"│ {line}", style="bold red"))

    body.append(Text("│"))
    footer = Text("└" + "─" * 69, style=style)
    body.append(footer)

    return Group(*body)


async def run_python(
    ctx: RunContext[RuneDependencies],
    code: str,
    *,
    timeout: int = 60,
) -> ToolResult:
    """
    Runs a Python code snippet in a persistent interactive interpreter.
    This tool allows you to execute Python code, with the state (variables, imports, etc.)
    persisting across multiple calls.

    Args:
        code (str): The Python code to execute.
        timeout (int, optional): The timeout in seconds. Defaults to 60.

    Returns:
        The result of the execution, including stdout, stderr, and any return values or display data.
    """
    client = _get_kernel_client()
    msg_id = client.execute(code)

    outputs: list[dict[str, Any]] = []
    is_dirty = False

    def set_dirty():
        nonlocal is_dirty
        is_dirty = True

    def build_frame():
        nonlocal is_dirty
        is_dirty = False
        return _create_renderable(code, outputs)

    async def message_handler():
        while True:
            try:
                # Use a small timeout to allow the outer timeout logic to work correctly
                msg = await asyncio.to_thread(client.get_iopub_msg, timeout=0.05)
                if msg["parent_header"].get("msg_id") != msg_id:
                    continue

                msg_type = msg["header"]["msg_type"]
                content = msg["content"]

                if msg_type == "status" and content["execution_state"] == "idle":
                    break

                if msg_type == "stream":
                    outputs.append(
                        {
                            "type": "stream",
                            "name": content.get("name"),
                            "text": content.get("text"),
                        }
                    )
                elif msg_type == "execute_result":
                    outputs.append(
                        {"type": "execute_result", "data": content.get("data")}
                    )
                elif msg_type == "display_data":
                    outputs.append(
                        {"type": "display_data", "data": content.get("data")}
                    )
                elif msg_type == "error":
                    outputs.append(
                        {"type": "error", "traceback": content.get("traceback")}
                    )
                    break
                set_dirty()

            except Empty:
                # This is expected if no message is received within the timeout
                pass

    handler_task = asyncio.create_task(message_handler())
    timeout_task = asyncio.create_task(asyncio.sleep(timeout))

    done, pending = await asyncio.wait(
        {handler_task, timeout_task}, return_when=asyncio.FIRST_COMPLETED
    )

    if handler_task in pending:
        handler_task.cancel()
    if timeout_task in pending:
        timeout_task.cancel()

    if timeout_task in done:
        if _kernel_manager:
            _kernel_manager.interrupt_kernel()
        raise asyncio.TimeoutError("Execution timed out")

    try:
        await handler_task
    except asyncio.CancelledError:
        # This is expected if the timeout was hit and the task was cancelled.
        # We still want to raise the timeout error that the test expects.
        if _kernel_manager:
            _kernel_manager.interrupt_kernel()
        raise asyncio.TimeoutError("Execution timed out") from None

    error_output = next((o for o in outputs if o["type"] == "error"), None)
    if error_output:
        traceback_str = "\n".join(error_output.get("traceback", []))
        raise ValueError(traceback_str)

    return ToolResult(
        data={"outputs": outputs},
        renderable=_create_renderable(code, outputs),
    )
