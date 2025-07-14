from __future__ import annotations

import pytest

from rune.tools.run_command import run_command

async def test_run_command_success(mock_run_context) -> None:
    result = await run_command(mock_run_context, "echo hello")
    assert result.data["exit_code"] == 0
    assert result.data["stdout"].strip() == "hello"


async def test_run_command_error(mock_run_context) -> None:
    with pytest.raises(ValueError):
        await run_command(mock_run_context, "ls non_existent_dir")


async def test_run_command_timeout(mock_run_context) -> None:
    with pytest.raises(TimeoutError):
        await run_command(mock_run_context, "sleep 0.2", timeout=0.1)


async def test_run_command_background(mock_run_context) -> None:
    result = await run_command(mock_run_context, "echo 'background command'", background=True)
    assert "pid" in result.data
    assert "log_file" in result.data
