from __future__ import annotations

import pytest
from pathlib import Path

from rune.tools.read_chunk import read_chunk
from pydantic_ai import RunContext
from pydantic_ai.usage import Usage
from rune.core.context import SessionContext


def test_read_chunk_success(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mock_run_context: RunContext[SessionContext]) -> None:
    monkeypatch.chdir(tmp_path)
    mock_run_context.deps.current_working_dir = tmp_path
    file_content = "hello world, this is a test of the read_chunk functionality."
    (tmp_path / "test_file.txt").write_text(file_content)

    # Read the first 5 bytes
    result = read_chunk(mock_run_context, "test_file.txt", length=5)
    assert result.status == "success"
    assert result.data["content"] == "hello"
    assert result.data["offset"] == 0
    assert result.data["read_length"] == 5
    assert result.data["more"] is True

    # Read from an offset
    result = read_chunk(mock_run_context, "test_file.txt", length=5, offset=6)
    assert result.data["content"] == "world"
    assert result.data["more"] is True

    # Read until the end
    result = read_chunk(mock_run_context, "test_file.txt", length=100, offset=len(file_content) - 12)
    assert result.data["content"] == "nctionality."
    assert result.data["read_length"] == 12
    assert result.data["more"] is False


def test_read_chunk_offset_beyond_eof(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mock_run_context: RunContext[SessionContext]) -> None:
    monkeypatch.chdir(tmp_path)
    mock_run_context.deps.current_working_dir = tmp_path
    (tmp_path / "test_file.txt").write_text("hello")

    result = read_chunk(mock_run_context, "test_file.txt", offset=10)
    assert result.status == "success"
    assert result.data["content"] == ""
    assert result.data["read_length"] == 0


def test_read_chunk_file_not_found(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mock_run_context: RunContext[SessionContext]) -> None:
    monkeypatch.chdir(tmp_path)
    mock_run_context.deps.current_working_dir = tmp_path
    with pytest.raises(FileNotFoundError):
        read_chunk(mock_run_context, "non_existent.txt")


def test_read_chunk_is_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mock_run_context: RunContext[SessionContext]) -> None:
    monkeypatch.chdir(tmp_path)
    mock_run_context.deps.current_working_dir = tmp_path
    (tmp_path / "a_dir").mkdir()
    with pytest.raises(IsADirectoryError):
        read_chunk(mock_run_context, "a_dir")


def test_read_chunk_outside_project_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mock_run_context: RunContext[SessionContext]) -> None:
    monkeypatch.chdir(tmp_path)
    mock_run_context.deps.current_working_dir = tmp_path
    
    import os
    if os.name == 'nt':
        pytest.skip("Permission test not applicable on Windows.")

    try:
        outside_file = Path("/tmp/test_file_for_chunk.txt")
        outside_file.write_text("content")
    except OSError as e:
        pytest.skip(f"Cannot write to /tmp for permission test: {e}")

    with pytest.raises(PermissionError):
        read_chunk(mock_run_context, str(outside_file))

    try:
        outside_file.unlink()
    except OSError:
        pass
