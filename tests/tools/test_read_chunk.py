from __future__ import annotations

import pytest
from pathlib import Path

from rune.tools.read_chunk import read_chunk


@pytest.mark.asyncio
async def test_read_chunk_success(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    file_content = "hello world, this is a test of the read_chunk functionality."
    (tmp_path / "test_file.txt").write_text(file_content)

    # Read the first 5 bytes
    result = await read_chunk("test_file.txt", length=5)
    assert result.data["content"] == "hello"
    assert result.data["offset"] == 0
    assert result.data["read_length"] == 5
    assert result.data["more"] is True

    # Read from an offset
    result = await read_chunk("test_file.txt", length=5, offset=6)
    assert result.data["content"] == "world"
    assert result.data["more"] is True

    # Read until the end
    result = await read_chunk("test_file.txt", length=100, offset=len(file_content) - 12)
    assert result.data["content"] == "nctionality."
    assert result.data["read_length"] == 12
    assert result.data["more"] is False


@pytest.mark.asyncio
async def test_read_chunk_offset_beyond_eof(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "test_file.txt").write_text("hello")

    result = await read_chunk("test_file.txt", offset=10)
    assert result.data["content"] == ""
    assert result.data["read_length"] == 0


@pytest.mark.asyncio
async def test_read_chunk_file_not_found(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    with pytest.raises(FileNotFoundError):
        await read_chunk("non_existent.txt")


@pytest.mark.asyncio
async def test_read_chunk_is_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "a_dir").mkdir()
    with pytest.raises(IsADirectoryError):
        await read_chunk("a_dir")


@pytest.mark.asyncio
async def test_read_chunk_outside_project_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    
    import os
    if os.name == 'nt':
        pytest.skip("Permission test not applicable on Windows.")

    try:
        outside_file = Path("/tmp/test_file_for_chunk.txt")
        outside_file.write_text("content")
    except OSError as e:
        pytest.skip(f"Cannot write to /tmp for permission test: {e}")

    with pytest.raises(PermissionError):
        await read_chunk(str(outside_file))

    try:
        outside_file.unlink()
    except OSError:
        pass
