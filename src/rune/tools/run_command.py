from __future__ import annotations

import asyncio
import os
import subprocess
import tempfile
from pathlib import Path

from pydantic_ai import RunContext
from rich.console import Group
from rich.syntax import Syntax
from rich.text import Text

from rune.adapters.ui import render as ui
from rune.core.context import SessionContext
from rune.core.tool_result import ToolResult
from rune.tools.registry import register_tool
from rune.utils.stream import stream_to_live


def _create_renderable_content(
    command: str,
    stdout_lines: list[str],
    stderr_lines: list[str],
) -> Group:
    """Creates the rich renderable for the command's output CONTENT only."""
    renderables = []

    renderables.append(Text(f"$ {command}", style="bold cyan"))

    stdout = "".join(stdout_lines)
    stderr = "".join(stderr_lines)

    if stdout:
        renderables.append(Text("\nSTDOUT " + "─" * 59, style="bold grey70"))
        renderables.append(
            Syntax(stdout, "bash", theme="ansi_dark", background_color="default")
        )

    if stderr:
        renderables.append(Text("\nSTDERR " + "─" * 59, style="bold yellow"))
        renderables.append(
            Syntax(stderr, "bash", theme="ansi_dark", background_color="default")
        )

    return Group(*renderables)


async def _handle_streaming_command(
    command: str, cwd: Path, timeout: int, live_manager
) -> ToolResult:
    """The core logic for running a command and streaming its output."""
    proc = await asyncio.create_subprocess_shell(
        command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=cwd,
    )

    stdout_lines: list[str] = []
    stderr_lines: list[str] = []
    is_dirty = True  # Start dirty to render initial frame

    def set_dirty():
        nonlocal is_dirty
        is_dirty = True

    async def read_stream(stream, sink: list[str]):
        """Reads from a stream, appends to sink, and sets the dirty flag."""
        if not stream:
            return
        while not stream.at_eof():
            line_bytes = await stream.readline()
            if not line_bytes:
                break
            line = line_bytes.decode("utf-8", errors="replace")
            sink.append(line)
            set_dirty()

    def build_frame():
        nonlocal is_dirty
        is_dirty = False
        content_update = _create_renderable_content(command, stdout_lines, stderr_lines)
        temp_status = ToolResult(status="success", data=None)
        return ui._build_tool_result_renderable(
            "run_command", temp_status, content_override=content_update
        )

    reader_tasks = asyncio.gather(
        read_stream(proc.stdout, stdout_lines),
        read_stream(proc.stderr, stderr_lines),
    )

    try:
        if live_manager:
            async with stream_to_live(live_manager, build_frame, lambda: is_dirty):
                await asyncio.wait_for(reader_tasks, timeout)
        else:
            await asyncio.wait_for(reader_tasks, timeout)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        raise TimeoutError(f"Command timed out after {timeout} seconds.")

    exit_code = await proc.wait()
    final_stdout = "".join(stdout_lines)
    final_stderr = "".join(stderr_lines)

    if exit_code != 0:
        error_details = (
            f"Command failed with exit code {exit_code}.\n"
            f"Stdout: {final_stdout.strip()}\n"
            f"------------------------------------\n"
            f"Stderr: {final_stderr.strip()}"
        )
        raise ValueError(error_details)

    return ToolResult(
        data={
            "command": command,
            "stdout": final_stdout,
            "stderr": final_stderr,
            "exit_code": exit_code,
        },
        renderable=_create_renderable_content(command, stdout_lines, stderr_lines),
    )


def _handle_background_command(
    command: str, session_ctx: SessionContext
) -> ToolResult:
    """Handles running a command in the background."""
    log_dir = session_ctx.current_working_dir / ".rune" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    tmp_log_fd, tmp_log_path_str = tempfile.mkstemp(dir=log_dir, text=True)
    tmp_log_path = Path(tmp_log_path_str)

    try:
        proc = subprocess.Popen(
            command,
            stdout=tmp_log_fd,
            stderr=subprocess.STDOUT,
            cwd=session_ctx.current_working_dir,
            shell=True,
            start_new_session=True,
        )
    finally:
        os.close(tmp_log_fd)

    pid = proc.pid
    log_file = log_dir / f"{pid}.log"
    tmp_log_path.rename(log_file)
    rel_log_path = str(log_file.relative_to(session_ctx.current_working_dir))

    return ToolResult(
        data={"pid": pid, "log_file": rel_log_path, "status": "success"},
        renderable=Text(
            f"✓ Started background command (PID: {pid}). Log: {rel_log_path}",
            style="green",
        ),
    )


@register_tool(needs_ctx=True)
async def run_command(
    ctx: RunContext[SessionContext],
    command: str,
    *,
    timeout: int = 60,
    background: bool = False,
) -> ToolResult:
    """
    Executes a bash command with live streaming output and an optional timeout.

    This tool can run commands in three modes:
    1.  **Synchronous (default):** Executes the command and streams its stdout and stderr
        to the UI in real-time. It waits for the command to complete.
    2.  **Background (`background=True`):** Starts the command and immediately returns,
        allowing it to run in the background. Ideal for long-running processes like web
        servers. Output is redirected to a log file.

    Args:
        command (str): The command to execute.
        timeout (int, optional): The timeout in seconds for synchronous commands.
            Defaults to 60.
        background (bool, optional): If True, runs the command in the background.
            Defaults to False.

    Returns:
        The final result of the command. For synchronous commands, this includes all
        output and the exit code. For background commands, this includes the PID and
        log file path.
    """
    session_ctx = ctx.deps

    if background:
        return _handle_background_command(command, session_ctx)

    # The default case is to stream the command's output.
    live_manager = session_ctx.live_display
    return await _handle_streaming_command(
        command, session_ctx.current_working_dir, timeout, live_manager
    )
