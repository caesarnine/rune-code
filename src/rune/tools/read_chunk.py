from __future__ import annotations

from pathlib import Path

from rich.console import Group
from rich.syntax import Syntax
from rich.text import Text

from rune.core.tool_result import ToolResult
from rune.tools.registry import register_tool


def _fmt_size(size: int) -> str:
    num = float(size)
    for unit in ("B", "KB", "MB", "GB"):
        if abs(num) < 1024:
            return f"{num:3.1f} {unit}"
        num /= 1024
    return f"{num:.1f} TB"


def _create_renderable(
    path: str,
    content: str | None,
    offset: int,
    read_length: int,
    file_size: int,
    more: bool,
    error: str | None = None,
) -> Group:
    if error:
        header_text = f"┌─ ! Error reading chunk from {path} "
        header = Text(header_text + "─" * (70 - len(header_text)), style="bold red")
        error_line = Text(f"│  {error}", style="red")
        footer = Text("└" + "─" * 69, style="red")
        return Group(header, error_line, footer)

    header_text = f"┌─ 📄 {path} "
    header = Text(header_text + "─" * (70 - len(header_text)), style="bold cyan")

    lexer = Path(path).suffix.lstrip(".") or "text"
    syntax = Syntax(
        content or "", lexer, theme="monokai", line_numbers=True, start_line=1
    )

    file_size_str = _fmt_size(file_size)
    footer_content = f"[Bytes {offset}-{offset + read_length} of {file_size_str}] [More: {'Yes' if more else 'No'}]"
    footer_line = f"└─ {footer_content} "
    footer = Text(footer_line + "─" * (70 - len(footer_line)), style="cyan")

    return Group(header, syntax, footer)


@register_tool(needs_ctx=False)
def read_chunk(path: str, *, offset: int = 0, length: int = 65_536) -> ToolResult:
    """Reads a chunk of bytes from a file, starting at a specific offset.

    This tool is ideal for reading large files piece by piece. The content is
    decoded as UTF-8, with errors replaced.

    Args:
        path: The path to the file to read from.
        offset: The byte offset at which to start reading. Defaults to 0.
        length: The maximum number of bytes to read. Defaults to 65536.
    """
    base = Path.cwd()
    target = (base / path).resolve()

    try:
        target.relative_to(base)
    except ValueError as e:
        raise PermissionError("Path is outside the project directory.") from e

    if not target.exists():
        raise FileNotFoundError("File not found.")

    if not target.is_file():
        raise IsADirectoryError("Path is a directory, not a file.")

    file_size = target.stat().st_size
    if offset >= file_size:
        return ToolResult(
            data={
                "path": path,
                "content": "",
                "offset": offset,
                "read_length": 0,
                "file_size": file_size,
                "more": False,
            },
            renderable=_create_renderable(path, "", offset, 0, file_size, False),
        )

    with target.open("rb") as f:
        f.seek(offset)
        data = f.read(length)

    text = data.decode("utf-8", errors="replace")
    read_len = len(data)
    more = (offset + read_len) < file_size

    return ToolResult(
        data={
            "path": path,
            "content": text,
            "offset": offset,
            "read_length": read_len,
            "file_size": file_size,
            "more": more,
        },
        renderable=_create_renderable(path, text, offset, read_len, file_size, more),
    )
