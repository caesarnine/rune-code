from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pathspec
from rich.console import Group
from rich.text import Text

from rune.core.tool_result import ToolResult
from rune.tools.registry import register_tool


def _rich_lines(node: dict, prefix: str = "", is_last: bool = True) -> list[Text]:
    connector = "" if prefix == "" else ("└── " if is_last else "├── ")
    icon = "d" if node["type"] == "dir" else "f"
    style = "cyan" if node["type"] == "dir" else "white"

    lines = [Text(f"{prefix}{connector}{icon} {node['name']}", style=style)]
    if node["children"]:
        new_prefix = prefix + ("    " if is_last else "│   ")
        for i, child in enumerate(node["children"]):
            lines.extend(_rich_lines(child, new_prefix, i == len(node["children"]) - 1))
    return lines


def _create_renderable(
    root: dict | None,
    files_listed: int,
    files_ignored: int,
    error: str | None = None,
) -> Group:
    if error:
        return Group(Text(error, style="bold red"))

    if not root:
        return Group(Text("No files found.", style="yellow"))

    header = Text(f"Listing for: {root['path']}", style="bold green")
    footer = Text(
        f"\nListed {files_listed} items, ignored {files_ignored}.",
        style="grey50",
    )
    tree_lines = _rich_lines(root)
    return Group(header, *tree_lines, footer)


def _load_ignore_spec(start_dir: Path) -> pathspec.PathSpec:
    patterns: list[str] = [
        ".git/",
        ".venv/",
        "__pycache__/",
        ".pytest_cache/",
        ".ruff_cache/",
    ]

    current = start_dir.resolve()
    try:
        git_root_str = subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=current,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        git_root = Path(git_root_str).resolve()
    except (subprocess.CalledProcessError, FileNotFoundError):
        git_root = None

    # Walk up from the start_dir to the git_root (or filesystem root)
    while True:
        for fname in (".gitignore", ".runeignore"):
            f = current / fname
            if f.is_file():
                try:
                    patterns.extend(f.read_text().splitlines())
                except OSError:
                    pass  # Ignore files we can't read

        # Stop if we have reached the git root, or the filesystem root
        if (git_root and current == git_root) or current.parent == current:
            break
        current = current.parent

    return pathspec.PathSpec.from_lines("gitwildmatch", patterns)


@register_tool(needs_ctx=False)
def list_files(
    path: str = ".",
    *,
    recursive: bool = True,
    max_depth: int = 3,
) -> ToolResult:
    """Lists the files and directories in a given path, respecting .gitignore.

    This tool provides a tree-like view of the directory structure. It automatically
    ignores files and directories specified in .gitignore and a default set of
    patterns (e.g., .git, .venv).

    Args:
        path: The path to the directory to list. Defaults to the current directory.
        recursive: If True, lists files and directories recursively. Defaults to True.
        max_depth: The maximum depth for recursive listing. Defaults to 3.
    """
    base_dir = Path.cwd()
    target_dir = (base_dir / path).resolve()

    if not target_dir.is_dir():
        raise NotADirectoryError(f"Path '{path}' is not a directory.")

    ignore_spec = _load_ignore_spec(target_dir)
    files_listed, ignored = 0, 0

    def walk(cur: Path, depth: int) -> dict[str, Any] | None:
        nonlocal files_listed, ignored

        rel = cur.relative_to(base_dir)
        # Add a trailing slash to properly match directories
        path_to_check = str(rel) + ("/" if cur.is_dir() else "")
        if cur != target_dir and ignore_spec.match_file(path_to_check):
            ignored += 1
            return None

        if not recursive and depth > 1:
            return None

        children: list[dict[str, Any]] = []
        for item in sorted(cur.iterdir(), key=lambda p: (p.is_file(), p.name.lower())):
            rel_item = item.relative_to(base_dir)
            if ignore_spec.match_file(str(rel_item)):
                ignored += 1
                continue

            files_listed += 1
            if item.is_dir():
                child = (
                    walk(item, depth + 1)
                    if recursive and depth < max_depth
                    else {
                        "path": str(rel_item),
                        "name": item.name,
                        "type": "dir",
                        "children": [],
                    }
                )
                if child:
                    children.append(child)
            else:
                children.append(
                    {
                        "path": str(rel_item),
                        "name": item.name,
                        "type": "file",
                        "children": [],
                    }
                )

        return {
            "path": str(rel),
            "name": cur.name,
            "type": "dir",
            "children": children or [],
        }

    root_node = walk(target_dir, 1)
    files_listed += 1

    return ToolResult(
        data={
            "root": root_node,
            "files_listed": files_listed,
            "files_ignored": ignored,
        },
        renderable=_create_renderable(root_node, files_listed, ignored),
    )
