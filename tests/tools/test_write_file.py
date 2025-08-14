from __future__ import annotations

import pytest
from pathlib import Path

from rune.tools.write_file import write_file
from pydantic_ai import RunContext
from pydantic_ai.usage import Usage
from rune.core.context import SessionContext


def test_write_file_create_new(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mock_run_context: RunContext[SessionContext]) -> None:
    monkeypatch.chdir(tmp_path)
    mock_run_context.deps.current_working_dir = tmp_path
    result = write_file(mock_run_context, "new_file.txt", "hello world")
    assert result.status == "success"
    assert result.data["status"] == "created"
    assert (tmp_path / "new_file.txt").read_text() == "hello world"


def test_write_file_overwrite_existing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mock_run_context: RunContext[SessionContext]) -> None:
    monkeypatch.chdir(tmp_path)
    mock_run_context.deps.current_working_dir = tmp_path
    (tmp_path / "existing_file.txt").write_text("original")
    result = write_file(mock_run_context, "existing_file.txt", "overwrite")
    assert result.status == "success"
    assert result.data["status"] == "modified"
    assert (tmp_path / "existing_file.txt").read_text() == "overwrite"
    assert "-original" in result.data["diff"]
    assert "+overwrite" in result.data["diff"]


def test_write_file_append(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mock_run_context: RunContext[SessionContext]) -> None:
    monkeypatch.chdir(tmp_path)
    mock_run_context.deps.current_working_dir = tmp_path
    (tmp_path / "append_file.txt").write_text("first")
    result = write_file(mock_run_context, "append_file.txt", "_second", mode="a")
    assert result.status == "success"
    assert result.data["status"] == "appended"
    assert (tmp_path / "append_file.txt").read_text() == "first_second"


def test_write_file_no_change(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mock_run_context: RunContext[SessionContext]) -> None:
    monkeypatch.chdir(tmp_path)
    mock_run_context.deps.current_working_dir = tmp_path
    (tmp_path / "no_change.txt").write_text("content")
    result = write_file(mock_run_context, "no_change.txt", "content")
    assert result.status == "success"
    assert result.data["status"] == "unchanged"


def test_write_file_is_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mock_run_context: RunContext[SessionContext]) -> None:
    monkeypatch.chdir(tmp_path)
    mock_run_context.deps.current_working_dir = tmp_path
    (tmp_path / "a_dir").mkdir()
    with pytest.raises(IsADirectoryError):
        write_file(mock_run_context, "a_dir", "content")


def test_write_file_outside_project_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mock_run_context: RunContext[SessionContext]) -> None:
    monkeypatch.chdir(tmp_path)
    mock_run_context.deps.current_working_dir = tmp_path
    
    import os
    if os.name == 'nt':
        pytest.skip("Permission test not applicable on Windows.")

    with pytest.raises(PermissionError):
        write_file(mock_run_context, "/tmp/should_fail.txt", "content")
