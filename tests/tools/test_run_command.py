from __future__ import annotations

import pytest

from rune.tools.run_command import run_command

def test_run_command_success(mock_run_context) -> None:
    result = run_command(mock_run_context, "echo hello")
    assert result.data["exit_code"] == 0
    assert result.data["stdout"] == "hello\n"


def test_run_command_error(mock_run_context) -> None:
    with pytest.raises(ValueError):
        run_command(mock_run_context, "ls non_existent_dir")


def test_run_command_timeout(mock_run_context) -> None:
    with pytest.raises(TimeoutError):
        run_command(mock_run_context, "sleep 0.2", timeout=0.1)
