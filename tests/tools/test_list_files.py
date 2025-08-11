from __future__ import annotations

import pytest
from pathlib import Path

from rune.tools.list_files import list_files


@pytest.mark.asyncio
async def test_list_files_success(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "dir1").mkdir()
    (tmp_path / "file1.txt").write_text("a")
    (tmp_path / "dir1" / "file2.txt").write_text("b")

    result = await list_files()
    root = result.data["root"]
    assert root["name"] == tmp_path.name
    assert len(root["children"]) == 2
    # Order is dir, then file
    assert root["children"][0]["name"] == "dir1"
    assert root["children"][0]["type"] == "dir"
    assert len(root["children"][0]["children"]) == 1
    assert root["children"][1]["name"] == "file1.txt"


@pytest.mark.asyncio
async def test_list_files_recursive_false(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "dir1").mkdir()
    (tmp_path / "dir1" / "file2.txt").write_text("b")

    result = await list_files(recursive=False)
    root = result.data["root"]
    assert len(root["children"]) == 1
    assert root["children"][0]["name"] == "dir1"
    # No children because recursive is false
    assert len(root["children"][0]["children"]) == 0


@pytest.mark.asyncio
async def test_list_files_max_depth(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "d1").mkdir()
    (tmp_path / "d1" / "d2").mkdir()
    (tmp_path / "d1" / "d2" / "d3").mkdir()

    result = await list_files(max_depth=2)
    root = result.data["root"]
    # d1
    assert len(root["children"][0]["children"]) == 1 # d2
    assert len(root["children"][0]["children"][0]["children"]) == 0 # d3 is not listed


@pytest.mark.asyncio
async def test_list_files_path_is_not_a_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "file.txt").write_text("hello")
    with pytest.raises(NotADirectoryError):
        await list_files(path="file.txt")


@pytest.mark.asyncio
async def test_list_files_with_gitignore(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".gitignore").write_text("*.log\nbuild")
    (tmp_path / "file.txt").write_text("a")
    (tmp_path / "file.log").write_text("b")
    (tmp_path / "build").mkdir()
    (tmp_path / "build" / "artifact").write_text("c")

    result = await list_files()
    root = result.data["root"]
    # .gitignore, file.txt
    assert len(root["children"]) == 2
    child_names = {c["name"] for c in root["children"]}
    assert "file.txt" in child_names
    assert ".gitignore" in child_names
    assert "file.log" not in child_names
    assert "build" not in child_names
