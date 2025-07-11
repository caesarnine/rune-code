from __future__ import annotations

import shlex
import subprocess

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
    ctx: RunContext[SessionContext], command: str, *, timeout: int = 60
) -> ToolResult:
    """
    Executes a given bash command in a persistent shell session with optional timeout, ensuring proper handling and security measures.

    Before executing the command, please follow these steps:

    1. Directory Verification:
       - If the command will create new directories or files, first use the list_files tool to verify the parent directory exists and is the correct location
       - For example, before running "mkdir foo/bar", first use LS to check that "foo" exists and is the intended parent directory

    2. Command Execution:
       - Always quote file paths that contain spaces with double quotes (e.g., cd "path with spaces/file.txt")
       - Examples of proper quoting:
         - cd "/Users/name/My Documents" (correct)
         - cd /Users/name/My Documents (incorrect - will fail)
         - python "/path/with spaces/script.py" (correct)
         - python /path/with spaces/script.py (incorrect - will fail)
       - After ensuring proper quoting, execute the command.
       - Capture the output of the command.

    Args:
        command (str): The command to execute.
        timeout (int, optional): The timeout in seconds. Defaults to 60.

    Returns:
        The result of the command.
    """
    session_ctx = ctx.deps
    cmd_list = shlex.split(command)

    # Special handling for 'cd' command, which is a shell builtin
    if cmd_list[0] == "cd":
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
