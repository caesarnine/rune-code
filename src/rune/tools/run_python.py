from __future__ import annotations

import atexit
import base64
from queue import Empty
from typing import Any

from jupyter_client.manager import KernelManager
from rich.console import Group
from rich.syntax import Syntax
from rich.text import Text

from rune.core.tool_result import ToolResult
from rune.tools.registry import register_tool

_kernel_manager = None
_kernel_client = None


def _get_kernel_client():
    global _kernel_manager, _kernel_client
    if _kernel_manager is None:
        _kernel_manager = KernelManager()
        _kernel_manager.start_kernel()
        atexit.register(_shutdown_kernel)
    if _kernel_client is None:
        _kernel_client = _kernel_manager.client()
        _kernel_client.start_channels()
    return _kernel_client


def _shutdown_kernel():
    global _kernel_manager, _kernel_client
    if _kernel_client:
        _kernel_client.stop_channels()
        _kernel_client = None
    if _kernel_manager:
        _kernel_manager.shutdown_kernel()
        _kernel_manager = None


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
            for line in output["text"].strip().splitlines():
                line_style = "yellow" if output["name"] == "stderr" else "default"
                body.append(Text(f"│ {line}", style=line_style))
        elif output["type"] == "execute_result":
            for line in output["data"]["text/plain"].strip().splitlines():
                body.append(Text(f"│ {line}"))
        elif output["type"] == "display_data":
            if "image/png" in output["data"]:
                body.append(
                    Text(
                        f"│ [Image (PNG, {len(output['data']['image/png'])} bytes)]",
                        style="italic",
                    )
                )
            elif "text/plain" in output["data"]:
                for line in output["data"]["text/plain"].strip().splitlines():
                    body.append(Text(f"│ {line}", style="dim"))
        elif output["type"] == "error":
            for line in output["traceback"]:
                body.append(Text(f"│ {line}", style="bold red"))

    body.append(Text("│"))
    footer = Text("└" + "─" * 69, style=style)
    body.append(footer)

    return Group(*body)


@register_tool(needs_ctx=False)
def run_python(code: str, *, timeout: int = 60) -> ToolResult:
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

    outputs = []

    while True:
        try:
            msg = client.get_iopub_msg(timeout=timeout)
            if msg["parent_header"].get("msg_id") != msg_id:
                continue

            msg_type = msg["header"]["msg_type"]
            content = msg["content"]

            if msg_type == "status" and content["execution_state"] == "idle":
                break

            if msg_type == "stream":
                outputs.append(
                    {"type": "stream", "name": content["name"], "text": content["text"]}
                )
            elif msg_type == "execute_result":
                outputs.append({"type": "execute_result", "data": content["data"]})
            elif msg_type == "display_data":
                outputs.append({"type": "display_data", "data": content["data"]})
            elif msg_type == "error":
                outputs.append({"type": "error", "traceback": content["traceback"]})
                # break here because error is the last message
                break

        except Empty:
            raise TimeoutError(f"Execution timed out after {timeout} seconds.")

    error_output = next((o for o in outputs if o["type"] == "error"), None)
    if error_output:
        traceback_str = "\n".join(error_output["traceback"])
        raise ValueError(traceback_str)

    return ToolResult(
        data={"outputs": outputs},
        renderable=_create_renderable(code, outputs),
    )
