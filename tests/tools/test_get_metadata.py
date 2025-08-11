from __future__ import annotations

import pytest
from pathlib import Path

from rune.tools.get_metadata import get_metadata


@pytest.mark.asyncio
async def test_get_metadata_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "test_file.txt").write_text("hello")

    result = await get_metadata("test_file.txt")
    assert result.data["path"] == "test_file.txt"
    assert result.data["type"] == "file"
    assert result.data["size"] == 5


@pytest.mark.asyncio
async def test_get_metadata_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "test_dir").mkdir()

    result = await get_metadata("test_dir")
    assert result.data["path"] == "test_dir"
    assert result.data["type"] == "dir"


@pytest.mark.asyncio
async def test_get_metadata_not_found(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    with pytest.raises(FileNotFoundError):
        await get_metadata("non_existent_file.txt")


@pytest.mark.asyncio
async def test_get_metadata_outside_project_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    
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
        await get_metadata(str(outside_file))

    # Teardown
    try:
        outside_file.unlink()
    except OSError:
        pass
