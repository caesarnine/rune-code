from __future__ import annotations

import difflib
from pathlib import Path

from rich.console import Group
from rich.syntax import Syntax
from rich.text import Text

from rune.core.tool_result import ToolResult
from rune.tools.registry import register_tool
from rune.utils.diff import ApplyDiffResult, DiffApplyer


def _create_renderable(
    status: str,
    path: str,
    blocks_applied: int = 0,
    diff: str | None = None,
    error: str | None = None,
) -> Group:
    renderables: list = []
    header_content = ""
    header_style = ""

    if status == "error":
        header_content = f"! Error editing file: {path}"
        header_style = "bold red"
        if error:
            # Indent error for clarity
            renderables.append(Text(f"│  {error}", style="red"))
    elif status == "modified":
        plural = "s" if blocks_applied != 1 else ""
        header_content = f"Δ File modified: {path} ({blocks_applied} block{plural})"
        header_style = "bold blue"
    else:  # unchanged
        header_content = f"• File unchanged: {path}"
        header_style = "dim"

    header = Text(f"┌─ {header_content}", style=header_style)
    renderables.insert(0, header)

    if diff:
        renderables.append(Syntax(diff, "diff", theme="monokai"))

    # Use the color from the header style for the footer line
    base_style = header_style.split(" ")[-1] if header_style else "default"
    footer = Text("└" + "─" * (len(str(header.plain)) - 1), style=base_style)
    renderables.append(footer)

    return Group(*renderables)


@register_tool(needs_ctx=False)
def edit_file(path: str, diff: str) -> ToolResult:
    """
    Performs precise, robust edits to a file using one or more diff blocks. Returns the diff between the original and edited file.

    Always review the returned diff to ensure the changes are as expected (pay close attention to indentation and formatting).

    KEY FEATURES:
    - Applies blocks sequentially, stopping on the first error.
    - Each SEARCH block must match uniquely.
    - Intelligent matching is resilient to minor whitespace/indentation differences.
    - Provides detailed, actionable error messages if a patch fails.
    - Supports `...` for matching content with elided lines.

    DIFF BLOCK FORMAT:
    ```
    <<<<<<< SEARCH
    [Content to find and replace]
    =======
    [New content to insert]
    >>>>>>> REPLACE

    Always make sure you've read the file before attempting any edits.

    Args:
        path: The path to the file that will be edited.
        diff: A string containing one or more diff blocks that specify the edits.
    ```
    """
    base_dir = Path.cwd()
    target = (base_dir / path).resolve()

    try:
        target.relative_to(base_dir)
    except ValueError as e:
        raise PermissionError("Path is outside the project directory.") from e

    if not target.is_file():
        raise FileNotFoundError("File not found or is a directory.")

    original_content = target.read_text(encoding="utf-8")

    applyer = DiffApplyer()
    apply_result: ApplyDiffResult = applyer.apply_diff(original_content, diff)

    if not apply_result.success:
        fail = apply_result.failed_blocks[0]
        error_message = fail.error_reason
        if fail.best_match_snippet:
            error_message += (
                f"\n\nDid you mean to match this section (score "
                f"{fail.best_match_score:.1%})?\n"
                f"---\n{fail.context_snippet}\n---"
            )
        raise ValueError(error_message)

    final_content = apply_result.final_content or original_content
    if final_content == original_content:
        return ToolResult(
            data={"path": path, "status": "unchanged"},
            renderable=_create_renderable("unchanged", path),
        )

    target.write_text(final_content, encoding="utf-8")

    diff_text = difflib.unified_diff(
        original_content.splitlines(keepends=True),
        final_content.splitlines(keepends=True),
        fromfile=f"a/{path}",
        tofile=f"b/{path}",
    )
    diff_str = "".join(diff_text) or None

    return ToolResult(
        data={
            "path": path,
            "status": "modified",
            "blocks_applied": len(apply_result.applied_blocks),
            "diff": diff_str,
        },
        renderable=_create_renderable(
            "modified",
            path,
            blocks_applied=len(apply_result.applied_blocks),
            diff=diff_str,
        ),
    )
