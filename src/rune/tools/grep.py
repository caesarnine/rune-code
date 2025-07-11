from __future__ import annotations

import json
import shutil
import subprocess
from collections import defaultdict
from pathlib import Path
from typing import Any

from rich.console import Group
from rich.text import Text

from rune.core.tool_result import ToolResult
from rune.tools.registry import register_tool


def _create_renderable(
    pattern: str, results_by_file: dict[str, list[dict]], error: str | None = None
) -> Group | Text:
    if error:
        header_text = "┌─ ! Grep Error "
        header = Text(header_text + "─" * (70 - len(header_text)), style="bold red")
        error_line = Text(f"│  {error}", style="red")
        footer = Text("└" + "─" * 69, style="red")
        return Group(header, error_line, footer)

    num_matches = sum(
        1
        for lines in results_by_file.values()
        for line in lines
        if line["type"] == "match"
    )

    if num_matches == 0:
        return Text(f"○ No matches found for '{pattern}'.", style="dim")

    num_files = len(results_by_file)
    match_str = f"{num_matches} match{'es' if num_matches != 1 else ''}"
    file_str = f"{num_files} file{'s' if num_files != 1 else ''}"
    header_content = f"/ Found {match_str} for '{pattern}' in {file_str}"
    header_text = f"┌─ {header_content} "
    header = Text(header_text + "─" * (80 - len(header_text)), style="bold blue")

    body: list = [header, Text("│")]

    for i, (path, lines) in enumerate(results_by_file.items()):
        if i > 0:
            body.append(Text("│"))

        body.append(Text(f"│  · {path}", style="bold bright_cyan"))
        last_num = -1
        for ln in lines:
            if last_num != -1 and ln["line_number"] > last_num + 1:
                body.append(Text("│    ~ ~ ~", style="grey50"))

            prefix_style = "bold yellow" if ln["type"] == "match" else "grey50"
            prefix = Text(f"│  {ln['line_number']: >5} │ ", style=prefix_style)

            if ln["type"] == "context":
                body.append(
                    Text.assemble(
                        prefix, Text(ln["line_content"].rstrip("\n"), style="dim")
                    )
                )
            else:
                line_render = Text()
                b = ln["line_content"].encode("utf-8")
                idx = 0
                for s, e in sorted(ln["submatches"]):
                    line_render.append(b[idx:s].decode("utf-8", errors="replace"))
                    line_render.append(
                        Text(
                            b[s:e].decode("utf-8", errors="replace"),
                            style="bold white on #555555",
                        )
                    )
                    idx = e
                line_render.append(
                    b[idx:].decode("utf-8", errors="replace").rstrip("\n")
                )
                body.append(Text.assemble(prefix, line_render))
            last_num = ln["line_number"]

    body.append(Text("│"))
    footer = Text("└" + "─" * 79, style="blue")
    body.append(footer)

    return Group(*body)


@register_tool(needs_ctx=False)
def grep(
    pattern: str,
    *,
    path: str = ".",
    context: int = 2,
    case_sensitive: bool = False,
    glob: str | None = None,
) -> ToolResult:
    """Searches for a regex pattern in files using ripgrep (rg).

    This tool is a powerful wrapper around the 'rg' command-line utility,
    providing fast, recursive search with context and glob filtering.

    Args:
        pattern: The regular expression to search for.
        path: The directory or file path to search within. Defaults to the
            current working directory.
        context: The number of lines of context to include before and after
            each match. Defaults to 2.
        case_sensitive: If True, the search will be case-sensitive.
            Defaults to False (case-insensitive).
        glob: A glob pattern to filter which files are searched (e.g., "*.py").
            Defaults to None, searching all files.
    """
    if not shutil.which("rg"):
        raise FileNotFoundError(
            "ripgrep (rg) not found. Install: https://github.com/BurntSushi/ripgrep#installation"
        )

    base_dir = Path.cwd()
    search_root = (base_dir / path).resolve()

    try:
        search_root.relative_to(base_dir)
    except ValueError as e:
        raise PermissionError("Search path is outside the project directory.") from e

    cmd = ["rg", "--json", "--context", str(context)]
    if case_sensitive:
        cmd.append("--case-sensitive")
    if glob:
        cmd.extend(["--glob", glob])
    cmd.extend(["--", pattern, str(search_root)])

    proc = subprocess.run(
        cmd, capture_output=True, text=True, encoding="utf-8", timeout=30, check=False
    )

    if proc.returncode == 2:
        raise ValueError(f"ripgrep error: {proc.stderr.strip()}")

    if not proc.stdout.strip():
        return ToolResult(
            data={"pattern": pattern, "results_by_file": {}, "stats": {}},
            renderable=_create_renderable(pattern, {}),
        )

    results_by_file: dict[str, list[dict[str, Any]]] = defaultdict(list)
    stats: dict = {}

    for raw in proc.stdout.strip().splitlines():
        if not raw:
            continue
        jo = json.loads(raw)
        typ = jo["type"]
        data = jo["data"]

        if typ in ("match", "context"):
            fp = data["path"]["text"]
            results_by_file[fp].append(
                {
                    "type": typ,
                    "path": fp,
                    "line_number": data["line_number"],
                    "line_content": data["lines"]["text"],
                    "submatches": [
                        (m["start"], m["end"]) for m in data.get("submatches", [])
                    ],
                }
            )
        elif typ == "summary":
            stats = data

    return ToolResult(
        data={
            "pattern": pattern,
            "results_by_file": dict(results_by_file),
            "stats": stats,
        },
        renderable=_create_renderable(pattern, dict(results_by_file)),
    )
