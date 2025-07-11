from __future__ import annotations

from pathlib import Path

from rich.console import Group
from rich.syntax import Syntax
from rich.text import Text

from rune.core.tool_result import ToolResult
from rune.tools.registry import register_tool

MAX_READ = 5 * 1024 * 1024  # 5 MB


@register_tool(needs_ctx=False)
def read_file(path: str) -> ToolResult:
    """Reads the entire content of a file.

    This tool is suitable for reasonably sized text files (up to 5 MB). For
    larger files, use the `read_chunk` tool instead. The content is decoded
    as UTF-8, with errors replaced.

    Args:
        path: The path to the file to read.
    """
    base = Path.cwd()
    target = (base / path).resolve()

    if not target.exists():
        raise FileNotFoundError(f"File not found at {path}")

    if not target.is_file():
        raise IsADirectoryError(f"Path {path} is a directory, not a file.")

    try:
        target.relative_to(base)
    except ValueError as e:
        raise PermissionError("Path is outside the project directory.") from e

    size = target.stat().st_size
    if size > MAX_READ:
        raise ValueError(
            f"File size {size / 1024 / 1024:.2f} MB exceeds 5 MB. Use read_chunk."
        )

    content = target.read_text(encoding="utf-8", errors="replace")
    lexer = Path(path).suffix.lstrip(".") or "text"

    lines = content.splitlines()
    total_lines = len(lines)
    snippet_lines_count = 15
    snippet_content = "\n".join(lines[:snippet_lines_count])

    # Human-readable size
    size_bytes = target.stat().st_size
    if size_bytes < 1024:
        size_str = f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        size_str = f"{size_bytes / 1024:.1f} KB"
    else:
        size_str = f"{size_bytes / 1024 / 1024:.1f} MB"

    header = Text(f"┌─ 📄 {path} ({size_str})")

    syntax = Syntax(
        snippet_content,
        lexer,
        theme="monokai",
        line_numbers=True,
        start_line=1,
    )

    footer_text = (
        f"Showing {min(total_lines, snippet_lines_count)} of {total_lines} lines"
    )
    footer = Text(f"└─ [{footer_text}]")

    return ToolResult(
        data={"path": path, "content": content},
        renderable=Group(header, syntax, footer),
    )
