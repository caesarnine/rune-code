from __future__ import annotations

import stat
from datetime import datetime, timezone
from pathlib import Path

from rich.console import Group
from rich.text import Text

from rune.core.tool_result import ToolResult
from rune.tools.registry import register_tool


def _fmt_size(size: int | None) -> str:
    if size is None:
        return "N/A"
    num = float(size)
    for unit in ("B", "KB", "MB", "GB"):
        if abs(num) < 1024:
            return f"{num:3.1f} {unit}"
        num /= 1024
    return f"{num:.1f} TB"


def _create_renderable(
    path: str,
    type: str,
    size: int | None = None,
    mtime_utc: datetime | None = None,
    permissions: str | None = None,
    error: str | None = None,
) -> Group:
    if type == "not_found":
        header_text = f"┌─ ! {path} "
        header = Text(header_text + "─" * (70 - len(header_text)), style="bold red")
        error_line = Text(f"│    Error: {error}", style="red")
        footer = Text("└" + "─" * 69, style="red")
        return Group(header, error_line, footer)

    glyph_map = {"file": "·", "dir": "▸", "symlink": "→"}.get(type, "?")
    color = "cyan" if type in ["dir", "symlink"] else "default"

    header_text = f"┌─ {glyph_map} {path} "
    header = Text(header_text + "─" * (70 - len(header_text)), style=f"bold {color}")

    mtime_str = mtime_utc.strftime("%Y-%m-%d %H:%M:%S UTC") if mtime_utc else "N/A"

    details = [
        Text(f"│ {'Type':>12}: {type}"),
        Text(f"│ {'Size':>12}: {_fmt_size(size)}"),
        Text(f"│ {'Permissions':>12}: {permissions or 'N/A'}"),
        Text(f"│ {'Modified':>12}: {mtime_str}"),
    ]

    renderables = [header, Text("│")]
    renderables.extend(details)
    renderables.append(Text("│"))

    footer = Text("└" + "─" * 69, style=color)
    renderables.append(footer)

    return Group(*renderables)


@register_tool(needs_ctx=False)
def get_metadata(path: str) -> ToolResult:
    """Outputs the metadata of a file or directory.

    Retrieves details such as type (file, dir), size, permissions, and last
    modification time for a given path.

    Args:
        path: The path to the file or directory to describe.
    """
    base_dir = Path.cwd()
    target = (base_dir / path).resolve()

    try:
        target.relative_to(base_dir)
    except ValueError as e:
        raise PermissionError("Path is outside the project directory.") from e

    if not target.exists():
        raise FileNotFoundError("File or directory not found.")

    st = target.stat()
    entry_type = (
        "dir"
        if target.is_dir()
        else "file"
        if target.is_file()
        else "symlink"
        if target.is_symlink()
        else "other"
    )
    mtime_utc = datetime.fromtimestamp(st.st_mtime, timezone.utc)
    permissions = stat.filemode(st.st_mode)

    data = {
        "path": path,
        "type": entry_type,
        "size": st.st_size,
        "mtime_utc": mtime_utc.isoformat(),
        "permissions": permissions,
    }

    return ToolResult(
        data=data,
        renderable=_create_renderable(
            path=path,
            type=entry_type,
            size=st.st_size,
            mtime_utc=mtime_utc,
            permissions=permissions,
        ),
    )
