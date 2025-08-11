from __future__ import annotations
import pytest
from pathlib import Path

from rune.tools.edit_file import edit_file


@pytest.mark.asyncio
async def test_edit_file_success(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "test_file.txt").write_text("line1\nline2\nline3")

    diff = '''<<<<<<< SEARCH
line2
=======
new_line2
>>>>>>> REPLACE'''

    result = await edit_file("test_file.txt", diff)
    assert result.data["status"] == "modified"

    content = (tmp_path / "test_file.txt").read_text()
    assert content == "line1\nnew_line2\nline3"


@pytest.mark.asyncio
async def test_edit_file_not_found(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    with pytest.raises(FileNotFoundError):
        await edit_file("non_existent_file.txt", "diff")


@pytest.mark.asyncio
async def test_edit_file_is_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "a_dir").mkdir()
    with pytest.raises(FileNotFoundError):
        await edit_file("a_dir", "diff")


@pytest.mark.asyncio
async def test_edit_file_bad_diff_syntax(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "test_file.txt").write_text("line1\nline2\nline3")
    
    bad_diff = "this is not a valid diff"
    with pytest.raises(ValueError, match="Invalid diff format"):
        await edit_file("test_file.txt", bad_diff)


@pytest.mark.asyncio
async def test_edit_file_search_block_not_found(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "test_file.txt").write_text("line1\nline2\nline3")
    
    diff_not_found = '''<<<<<<< SEARCH
this_is_not_in_the_file
=======
replacement
>>>>>>> REPLACE'''
    with pytest.raises(ValueError, match="No unique match found"):
        await edit_file("test_file.txt", diff_not_found)


@pytest.mark.asyncio
async def test_edit_file_outside_project_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    
    import os
    if os.name == 'nt':
        pytest.skip("Permission test is not applicable on Windows in this form.")
        
    # Create a file outside the project's directory, which is chdir'd to tmp_path
    # This might fail if we don't have perms to write to /tmp, but it's standard on unix-like systems.
    try:
        outside_file = Path("/tmp/test_file_for_edit.txt")
        outside_file.write_text("content")
    except OSError as e:
        pytest.skip(f"Could not write to /tmp to set up permission test: {e}")

    with pytest.raises(PermissionError, match="Path is outside the project directory"):
        await edit_file(str(outside_file), "diff")
        
    try:
        outside_file.unlink()
    except OSError:
        pass
