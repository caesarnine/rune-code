from __future__ import annotations

import os
import shlex
import subprocess
import tempfile

from rich.console import Group
from rich.syntax import Syntax
from rich.text import Text

from rune.core.tool_result import ToolResult
from rune.tools.registry import register_tool


def _create_renderable(
    command: str,
    stdout: str | None,
    stderr: str | None,
    exit_code: int,
    error: str | None = None,
) -> Group:
    renderables = []
    if error:
        header_text = "┌─ ! Command Execution Error "
        header = Text(header_text + "─" * (70 - len(header_text)), style="bold red")
        error_line = Text(f"│  {error}", style="red")
        footer = Text("└" + "─" * 69, style="red")
        return Group(header, error_line, footer)

    success = exit_code == 0
    glyph = "✔" if success else "✘"
    style = "green" if success else "red"
    header_content = (
        f"{glyph} Command {'Succeeded' if success else 'Failed'} (Exit {exit_code})"
    )
    header_text = f"┌─ {header_content} "
    header = Text(header_text + "─" * (70 - len(header_text)), style=f"bold {style}")
    renderables.append(header)

    renderables.append(Text(f"│  $ {command}", style="bold cyan"))

    if stdout:
        renderables.append(Text("│"))
        renderables.append(Text("│  STDOUT " + "─" * 59, style="bold grey70"))
        renderables.append(
            Syntax(stdout, "bash", theme="ansi_dark", background_color="default")
        )

    if stderr:
        renderables.append(Text("│"))
        renderables.append(Text("│  STDERR " + "─" * 59, style="bold yellow"))
        renderables.append(
            Syntax(stderr, "bash", theme="ansi_dark", background_color="default")
        )

    renderables.append(Text("└" + "─" * 69, style=style))

    return Group(*renderables)


from pathlib import Path

from pydantic_ai import RunContext

from rune.core.context import SessionContext


@register_tool(needs_ctx=True)
def run_command(
    ctx: RunContext[SessionContext],
    command: str,
    *,
    timeout: int = 60,
    background: bool = False,
) -> ToolResult:
    """
    Executes a given bash command in a persistent shell session with optional timeout, ensuring proper handling and security measures.

    This tool can run commands in two modes:
    1.  **Synchronous (default):** Waits for the command to complete and returns its output.
    2.  **Background (`background=True`):** Starts the command and immediately returns, allowing it to run in the background. This is ideal for long-running processes like web servers or file watchers.

    When running in the background:
    - The command's output (`stdout` and `stderr`) is redirected to a log file in the `.rune/logs` directory, named after the process ID (PID).
    - The tool returns a dictionary containing the PID and the path to the log file, which you can use to monitor or stop the process.

    **NOTE:** The `cd` command is a shell built-in and cannot be executed in the background.

    Args:
        command (str): The command to execute.
        timeout (int, optional): The timeout in seconds for synchronous commands. Defaults to 60.
        background (bool, optional): If True, runs the command in the background. Defaults to False.

    Returns:
        The result of the command. For background commands, this includes the PID and log file path.
    """
    session_ctx = ctx.deps
    cmd_list = shlex.split(command)

    # Special handling for 'cd' command, which is a shell builtin
    if cmd_list[0] == "cd":
        if background:
            raise ValueError("'cd' command cannot be run in the background.")
        if len(cmd_list) == 1:
            # 'cd' with no arguments can be treated as a no-op or go to home.
            # For simplicity, we'll treat as no-op.
            target_dir = Path.home()
        else:
            target_dir = Path(cmd_list[1])

        # Resolve the new path based on the current context
        new_dir = (session_ctx.current_working_dir / target_dir).resolve()

        if not new_dir.is_dir():
            raise ValueError(f"cd: no such file or directory: {new_dir}")

        session_ctx.current_working_dir = new_dir
        return ToolResult(
            data={"status": "success", "message": f"Changed directory to {new_dir}"},
            renderable=Text(f"✓ Changed directory to {new_dir}", style="green"),
        )

    if background:
        log_dir = session_ctx.current_working_dir / ".rune" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)

        # Create a temporary file to redirect output to, then rename it to the PID.
        # This avoids a race condition where we need the PID to name the file but don't have it yet.
        tmp_log_fd, tmp_log_path_str = tempfile.mkstemp(dir=log_dir, text=True)
        tmp_log_path = Path(tmp_log_path_str)

        try:
            proc = subprocess.Popen(
                cmd_list,
                shell=False,
                stdout=tmp_log_fd,
                stderr=subprocess.STDOUT,
                cwd=session_ctx.current_working_dir,
                start_new_session=True,  # Detach from this process group
            )
        finally:
            # The file descriptor is now owned by the Popen object, close our copy
            os.close(tmp_log_fd)

        pid = proc.pid
        log_file = log_dir / f"{pid}.log"
        tmp_log_path.rename(log_file)

        return ToolResult(
            data={
                "pid": pid,
                "log_file": str(log_file.relative_to(session_ctx.current_working_dir)),
                "command": command,
                "status": "success",
            },
            renderable=Text(f"✓ Started background command (PID: {pid}). Log: {log_file}", style="green"),
        )

    try:
        proc = subprocess.run(
            cmd_list,
            shell=False,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            cwd=session_ctx.current_working_dir,
        )

        if proc.returncode != 0:
            error_details = (
                f"Command failed with exit code {proc.returncode}.\n"
                f"Stdout: {proc.stdout.strip()}\n"
                f"------------------------------------"
                f"Stderr: {proc.stderr.strip()}"
            )
            raise ValueError(error_details)
        # This part is now only the success path.
        return ToolResult(
            data={
                "command": command,
                "stdout": proc.stdout,
                "stderr": proc.stderr,
                "exit_code": proc.returncode,
            },
            renderable=_create_renderable(
                command=command,
                stdout=proc.stdout,
                stderr=proc.stderr,
                exit_code=proc.returncode,
            ),
        )

    except subprocess.TimeoutExpired:
        # Re-raise with a clearer message for the LLM.
        raise TimeoutError(f"Command timed out after {timeout} seconds.")
