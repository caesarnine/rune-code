from __future__ import annotations

import pytest
from pathlib import Path

from rune.tools.get_metadata import get_metadata
from pydantic_ai import RunContext
from pydantic_ai.usage import Usage
from rune.core.context import SessionContext


def test_get_metadata_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mock_run_context: RunContext[SessionContext]) -> None:
    monkeypatch.chdir(tmp_path)
    mock_run_context.deps.current_working_dir = tmp_path
    (tmp_path / "test_file.txt").write_text("hello")

    result = get_metadata(mock_run_context, "test_file.txt")
    assert result.status == "success"
    assert result.data["path"] == "test_file.txt"
    assert result.data["type"] == "file"
    assert result.data["size"] == 5


def test_get_metadata_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mock_run_context: RunContext[SessionContext]) -> None:
    monkeypatch.chdir(tmp_path)
    mock_run_context.deps.current_working_dir = tmp_path
    (tmp_path / "test_dir").mkdir()

    result = get_metadata(mock_run_context, "test_dir")
    assert result.status == "success"
    assert result.data["path"] in {"test_dir", "."}
    assert result.data["type"] == "dir"


def test_get_metadata_not_found(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mock_run_context: RunContext[SessionContext]) -> None:
    monkeypatch.chdir(tmp_path)
    mock_run_context.deps.current_working_dir = tmp_path
    with pytest.raises(FileNotFoundError):
        get_metadata(mock_run_context, "non_existent_file.txt")


def test_get_metadata_outside_project_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mock_run_context: RunContext[SessionContext]) -> None:
    monkeypatch.chdir(tmp_path)
    mock_run_context.deps.current_working_dir = tmp_path
    
    import os
    if os.name == 'nt':
        pytest.skip("Permission test is not applicable on Windows in this form.")

    # Setup outside file
    try:
        outside_file = Path("/tmp/test_file_for_metadata.txt")
        outside_file.write_text("content")
    except OSError as e:
        pytest.skip(f"Could not write to /tmp to set up permission test: {e}")

    with pytest.raises(PermissionError, match="Path is outside the project directory"):
        get_metadata(mock_run_context, str(outside_file))

    # Teardown
    try:
        outside_file.unlink()
    except OSError:
        pass
