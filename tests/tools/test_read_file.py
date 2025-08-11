from __future__ import annotations

import os
import pytest
from pathlib import Path

from rune.tools.read_file import read_file


@pytest.mark.asyncio
async def test_read_file_success(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    test_file = tmp_path / "test_file.txt"
    with open(test_file, "w") as f:
        f.write("hello world")

    result = await read_file("test_file.txt")
    assert result.data["content"] == "hello world"


@pytest.mark.asyncio
async def test_read_file_not_found(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    # Use pytest.raises to assert that an exception is thrown.
    with pytest.raises(FileNotFoundError) as exc_info:
        await read_file("non_existent_file.txt")

    # Optionally, assert on the exception message.
    assert "File not found" in str(exc_info.value)


@pytest.mark.asyncio
async def test_read_file_is_directory(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "a_dir").mkdir()
    with pytest.raises(IsADirectoryError):
        await read_file("a_dir")


@pytest.mark.asyncio
async def test_read_file_too_large(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "large_file.txt").write_bytes(b"a" * (6 * 1024 * 1024))
    with pytest.raises(ValueError, match="exceeds 5 MB"):
        await read_file("large_file.txt")


@pytest.mark.asyncio
async def test_read_file_outside_project_directory(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)

    if os.name == "nt":
        pytest.skip("Permission test not applicable on Windows.")

    try:
        outside_file = (tmp_path.parent / "outside_file.txt")
        outside_file.write_text("content")
    except OSError as e:
        pytest.skip(f"Could not write to parent dir for permission test: {e}")

    with pytest.raises(PermissionError):
        await read_file(str(outside_file))

    try:
        outside_file.unlink()
    except OSError:
        pass
