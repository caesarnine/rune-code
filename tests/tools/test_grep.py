from __future__ import annotations

import pytest
from pathlib import Path
import shutil

from rune.tools.grep import grep


@pytest.fixture(scope="module", autouse=True)
def check_ripgrep_installed():
    if not shutil.which("rg"):
        pytest.skip("ripgrep (rg) is not installed, skipping grep tests.")


def test_grep_success(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "test_file.txt").write_text("hello world\nHELLO AGAIN")

    # Case-insensitive by default
    result = grep("hello", path=str(tmp_path))
    assert result.status == "success"
    results = result.data["results_by_file"]
    test_file_path = str(tmp_path / "test_file.txt")
    assert test_file_path in results
    assert len(results[test_file_path]) == 2
    assert results[test_file_path][0]["line_content"].strip() == "hello world"


def test_grep_case_sensitive(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "test_file.txt").write_text("hello world")

    result = grep("hello", path=str(tmp_path), case_sensitive=True)
    assert result.status == "success"
    results = result.data["results_by_file"]
    test_file_path = str(tmp_path / "test_file.txt")
    assert len(results[test_file_path]) == 1


def test_grep_no_matches(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "test_file.txt").write_text("hello world")

    result = grep("non_existent_pattern", path=str(tmp_path))
    assert result.status == "success"
    assert not result.data["results_by_file"]


def test_grep_with_glob(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "test_file.txt").write_text("hello world")
    (tmp_path / "another_file.log").write_text("hello log")

    result = grep("hello", path=str(tmp_path), glob="*.txt")
    assert result.status == "success"
    results = result.data["results_by_file"]
    assert str(tmp_path / "test_file.txt") in results
    assert "another_file.log" not in results


def test_grep_invalid_regex(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ValueError, match="ripgrep error"):
        grep("(*)", path=str(tmp_path))


def test_grep_path_outside_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # This test doesn't create a file outside, it just uses a path that
    # when resolved, would be outside the chdir'd tmp_path.
    monkeypatch.chdir(tmp_path)
    with pytest.raises(PermissionError):
        grep("hello", path="/tmp")
