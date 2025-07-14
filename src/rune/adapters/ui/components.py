# new file
from __future__ import annotations

from io import StringIO

from rich.console import Console, Group, RenderableType
from rich.table import Table
from rich.text import Text

from .console import console as default_console


def bar_frame(
    body: RenderableType,
    *,
    glyph: str,
    bar_style: str,
    indent: str = "  ",
    console: Console = default_console,
) -> Group:
    """
    Wrap *body* with a coloured gutter and indent so callers
    never touch bar-rendering again.
    """
    # Render *body* into a table grid the same way _build_tool_result_renderable does,    # but in one reusable place.
    content_grid = Table.grid(expand=True)
    bar_width = len(glyph) + 1  # glyph + space
    content_grid.add_column(width=bar_width)
    content_grid.add_column(width=len(indent))
    content_grid.add_column(ratio=1)

    bar_text = Text.from_markup(f"[{bar_style}]{glyph}[/] ")
    indent_text = Text(indent)

    # Render content to an in-memory console to get its lines
    content_width = console.width - bar_width - len(indent)
    capture_buffer = StringIO()
    capture_console = Console(
        file=capture_buffer,
        force_terminal=True,
        color_system=console.color_system,
        width=content_width,
    )
    capture_console.print(body)
    output_lines = capture_buffer.getvalue().splitlines()

    for line in output_lines:
        content_line = Text.from_ansi(line)
        content_grid.add_row(bar_text, indent_text, content_line)

    return Group(content_grid)
