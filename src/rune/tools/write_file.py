from __future__ import annotations

import difflib
from pathlib import Path
from typing import Literal

from rich.console import Group
from rich.syntax import Syntax
from rich.text import Text

from rune.core.tool_result import ToolResult
from rune.tools.registry import register_tool


def _create_renderable(
    status: str,
    path: str,
    bytes_written: int = 0,
    diff: str | None = None,
    error: str | None = None,
) -> Group:
    renderables: list = []
    header_content = ""
    header_style = ""

    if status == "error":
        header_content = f"! Error writing file: {path}"
        header_style = "bold red"
        if error:
            renderables.append(Text(f"│  {error}", style="red"))
    elif status == "created":
        header_content = f"+ File created: {path} ({bytes_written:,} bytes)"
        header_style = "bold green"
    elif status == "modified":
        header_content = f"Δ File modified: {path} ({bytes_written:,} bytes)"
        header_style = "bold blue"
    elif status == "appended":
        header_content = f"» Appended to file: {path} ({bytes_written:,} bytes)"
        header_style = "bold green"
    elif status == "unchanged":
        header_content = f"• File unchanged: {path}"
        header_style = "dim"

    header_plain_text = f"┌─ {header_content}"
    header = Text(header_plain_text, style=header_style)
    renderables.insert(0, header)

    if diff:
        renderables.append(
            Syntax(diff, "diff", theme="monokai", background_color="default")
        )

    base_style = header_style.split(" ")[-1] if header_style else "default"
    footer = Text("└" + "─" * (len(header_plain_text) - 1), style=base_style)
    renderables.append(footer)

    return Group(*renderables)


@register_tool(needs_ctx=False)
def write_file(path: str, content: str, *, mode: Literal["w", "a"] = "w") -> ToolResult:
    """Writes or appends content to a file on the local filesystem.

    This tool can create a new file, overwrite an existing file, or append
    content to the end of an existing file. If the parent directories for the
    given path do not exist, they will be created automatically. When
    overwriting, a diff of the changes is returned.

    Args:
        path: The path to the file to be written to.
        content: The string content to write to the file.
        mode: The write mode. Can be one of two values:
            'w': Overwrite the file if it exists, or create it if it does not.
                 This is the default.
            'a': Append the content to the end of the file, creating it if it
                 does not exist.
    """
    base = Path.cwd()
    target = (base / path).resolve()

    try:
        target.relative_to(base)
    except ValueError as e:
        raise PermissionError("Path is outside the project directory.") from e

    if target.is_dir():
        raise IsADirectoryError("Path is a directory, not a file.")

    target.parent.mkdir(parents=True, exist_ok=True)

    if mode == "a":
        with target.open("a", encoding="utf-8") as f:
            bytes_written = f.write(content)
        return ToolResult(
            data={
                "path": path,
                "status": "appended",
                "bytes_written": bytes_written,
            },
            renderable=_create_renderable(
                "appended", path, bytes_written=bytes_written
            ),
        )

    was_existing = target.exists()
    original = target.read_text(encoding="utf-8") if was_existing else ""
    if original == content:
        return ToolResult(
            data={"path": path, "status": "unchanged"},
            renderable=_create_renderable("unchanged", path),
        )

    with target.open("w", encoding="utf-8") as f:
        bytes_written = f.write(content)

    diff_lines = difflib.unified_diff(
        original.splitlines(keepends=True),
        content.splitlines(keepends=True),
        fromfile=f"a/{path}",
        tofile=f"b/{path}",
    )
    diff_str = "".join(diff_lines) or None
    status = "modified" if was_existing else "created"

    return ToolResult(
        data={
            "path": path,
            "status": status,
            "bytes_written": bytes_written,
            "diff": diff_str,
        },
        renderable=_create_renderable(
            status, path, bytes_written=bytes_written, diff=diff_str
        ),
    )
