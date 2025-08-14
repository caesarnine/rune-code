from __future__ import annotations

import pytest
from pathlib import Path

from rune.tools.list_files import list_files
from pydantic_ai import RunContext
from pydantic_ai.usage import Usage
from rune.core.context import SessionContext


def test_list_files_success(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mock_run_context: RunContext[SessionContext]) -> None:
    monkeypatch.chdir(tmp_path)
    mock_run_context.deps.current_working_dir = tmp_path
    (tmp_path / "dir1").mkdir()
    (tmp_path / "file1.txt").write_text("a")
    (tmp_path / "dir1" / "file2.txt").write_text("b")

    result = list_files(mock_run_context)
    assert result.status == "success"
    root = result.data["root"]
    assert root["name"] in {tmp_path.name, "."}
    assert len(root["children"]) == 2
    # Order is dir, then file
    assert root["children"][0]["name"] == "dir1"
    assert root["children"][0]["type"] == "dir"
    assert len(root["children"][0]["children"]) == 1
    assert root["children"][1]["name"] == "file1.txt"


def test_list_files_recursive_false(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mock_run_context: RunContext[SessionContext]) -> None:
    monkeypatch.chdir(tmp_path)
    mock_run_context.deps.current_working_dir = tmp_path
    (tmp_path / "dir1").mkdir()
    (tmp_path / "dir1" / "file2.txt").write_text("b")

    result = list_files(mock_run_context, recursive=False)
    assert result.status == "success"
    root = result.data["root"]
    assert len(root["children"]) == 1
    assert root["children"][0]["name"] == "dir1"
    # No children because recursive is false
    assert len(root["children"][0]["children"]) == 0


def test_list_files_max_depth(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mock_run_context: RunContext[SessionContext]) -> None:
    monkeypatch.chdir(tmp_path)
    mock_run_context.deps.current_working_dir = tmp_path
    (tmp_path / "d1").mkdir()
    (tmp_path / "d1" / "d2").mkdir()
    (tmp_path / "d1" / "d2" / "d3").mkdir()

    result = list_files(mock_run_context, max_depth=2)
    assert result.status == "success"
    root = result.data["root"]
    # d1
    assert len(root["children"][0]["children"]) == 1 # d2
    assert len(root["children"][0]["children"][0]["children"]) == 0 # d3 is not listed


def test_list_files_path_is_not_a_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mock_run_context: RunContext[SessionContext]) -> None:
    monkeypatch.chdir(tmp_path)
    mock_run_context.deps.current_working_dir = tmp_path
    (tmp_path / "file.txt").write_text("hello")
    with pytest.raises(NotADirectoryError):
        list_files(mock_run_context, path="file.txt")


def test_list_files_with_gitignore(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mock_run_context: RunContext[SessionContext]) -> None:
    monkeypatch.chdir(tmp_path)
    mock_run_context.deps.current_working_dir = tmp_path
    (tmp_path / ".gitignore").write_text("*.log\nbuild")
    (tmp_path / "file.txt").write_text("a")
    (tmp_path / "file.log").write_text("b")
    (tmp_path / "build").mkdir()
    (tmp_path / "build" / "artifact").write_text("c")

    result = list_files(mock_run_context)
    assert result.status == "success"
    root = result.data["root"]
    # .gitignore, file.txt
    assert len(root["children"]) >= 2
    child_names = {c["name"] for c in root["children"]}
    assert "file.txt" in child_names
    assert ".gitignore" in child_names
    assert "file.log" not in child_names
    assert "build" not in child_names
