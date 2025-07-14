# src/rune/adapters/ui/render.py
from typing import Any

from rich.console import Group, RenderableType
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text

from rune.core.messages import ModelMessage

# Import ToolResult to type annotate
from rune.core.tool_result import ToolResult

from .components import bar_frame
from .console import console
from .glyphs import GLYPH, INDENT


def _serialise(o: Any) -> str:
    import dataclasses
    import json

    if dataclasses.is_dataclass(o):
        o = dataclasses.asdict(o)
    try:
        return json.dumps(o, default=str, indent=2)
    except TypeError:
        return str(o)


# ─────────────────────────── Display helpers ──────────────────────────


def _render_with_bar(
    text_to_render: str, bar_style_key: str, *, text_style: str | None = None
) -> None:
    """Renders a block of text with a vertical bar and optional text styling."""
    if not text_to_render.strip():
        return

    bar_char, bar_style = GLYPH[bar_style_key]
    body = (
        Text(text_to_render, style=text_style) if text_style else Text(text_to_render)
    )

    console.print(
        bar_frame(
            body,
            glyph=bar_char,
            bar_style=bar_style,
            indent=INDENT,
        )
    )


def display_tool_call(name: str, params: Any | None) -> None:
    glyph, style = GLYPH["tool_call"]
    bar_char, bar_style = GLYPH["tool_call_bar"]  # Use the tool's specific bar

    header = Text.from_markup(f"[{style}]{glyph}[/] [bold]{name}[/]")

    if params is None:
        body = header
    else:
        param_renderables = []
        if isinstance(params, dict):
            for key, val in params.items():
                line = Text(f"{key} = ", end="")
                line.append(Text(repr(val), style="cyan"))
                param_renderables.append(line)
        else:
            param_renderables.append(Text(str(params), style="cyan"))

        param_grid = Table.grid(expand=True)
        param_grid.add_column(width=len(INDENT))
        param_grid.add_column(ratio=1)
        for r in param_renderables:
            param_grid.add_row(INDENT, r)

        body = Group(header, param_grid)

    console.print(
        bar_frame(
            body,
            glyph=bar_char,
            bar_style=bar_style,
            indent="",
        )
    )


def _build_tool_result_renderable(
    name: str, res: ToolResult, content_override: RenderableType | None = None
) -> Table:
    """Builds the complete, framed renderable for a tool result."""
    is_error = res.status == "error"
    glyph_key = "tool_error" if is_error else "tool_result"
    bar_key = "tool_error_bar" if is_error else "tool_result_bar"

    glyph, style = GLYPH[glyph_key]
    bar_char, bar_style = GLYPH[bar_key]

    header_bar_prefix = f"[{bar_style}]{bar_char}[/] "
    header_text = f"{'error from' if is_error else 'result from'} {name}"
    header = Text.from_markup(f"{header_bar_prefix}[{style}]{glyph}[/] {header_text}")

    # Determine the content to render
    content_to_render: RenderableType
    if content_override is not None:
        content_to_render = content_override
    elif is_error:
        content_to_render = Text(res.error or "unknown error", style="bold red")
    elif res.renderable is not None:
        content_to_render = res.renderable
    else:
        content_to_render = Syntax(_serialise(res.data), "json", theme="ansi_dark")

    content_grid = bar_frame(
        content_to_render,
        glyph=bar_char,
        bar_style=bar_style,
        indent=INDENT,
    )

    # Group the header, a spacer, and the content grid into a single renderable
    frame_grid = Table.grid(expand=True)
    frame_grid.add_row(header)
    frame_grid.add_row(Text.from_markup(header_bar_prefix.rstrip()))  # Spacer
    frame_grid.add_row(content_grid)

    return frame_grid


def display_tool_result(name: str, res: ToolResult) -> None:
    """Builds and prints the standard tool result UI."""
    renderable = _build_tool_result_renderable(name, res)
    console.print(renderable)


def prose(role: str, text: str, *, glyph: bool = True) -> None:
    if not text:
        return

    # User messages are simple prefixed lines
    if role == "user":
        mark, style = GLYPH[role]
        console.print(f"[{style}]{mark}[/] {text}\n")
        return

    # Handle thinking and assistant messages with the bar
    if role == "thinking":
        bar_char, bar_style = GLYPH["thinking_bar"]
        bar_prefix = f"[{bar_style}]{bar_char}[/]"
        thinking_text, thinking_style = GLYPH["thinking_text"]
        # Print a blank line with bar, the thinking text, then the agent's thoughts
        console.print(bar_prefix)
        console.print(f"{bar_prefix} [{thinking_style}]{thinking_text}[/]")
        _render_with_bar(text, "thinking_bar", text_style=thinking_style)
    elif role == "assistant":
        # Print a blank line to separate from tools/thinking
        bar_char, bar_style = GLYPH["assistant_bar"]
        console.print(f"[{bar_style}]{bar_char}[/]")
        _render_with_bar(text, "assistant_bar")
        console.print()  # Final newline after assistant response


PREVIEW_TURNS = 3


def preview_history(msgs: list[ModelMessage]) -> None:
    if not msgs:
        return
    console.print("\n[dim]–– Resuming conversation ––[/dim]")
    turns = [m for m in msgs if m.role in {"user", "assistant"} and m.content]
    for m in turns[-PREVIEW_TURNS * 2 :]:
        # For preview, we just use a simplified renderer
        if m.role == "user":
            mark, style = GLYPH["user"]
            console.print(f"[{style}]{mark}[/] {m.content or ''}")
        else:
            console.print(f"[#af87ff]│[/] {m.content or ''}")

    console.print("[dim]–––––––––––––––––––––––––[/dim]\n")
