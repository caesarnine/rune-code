from __future__ import annotations

import pytest

from rune.tools.run_python import run_python

import asyncio

async def test_run_python_simple(mock_run_context) -> None:
    result = await run_python(mock_run_context, "print('hello')")
    assert result.status == "success"
    assert len(result.data["outputs"]) >= 1
    assert result.data["outputs"][0]["text"].strip() == "hello"


async def test_run_python_variable(mock_run_context) -> None:
    await run_python(mock_run_context, "x = 10")
    result = await run_python(mock_run_context, "print(x)")
    assert result.status == "success"
    assert len(result.data["outputs"]) >= 1
    assert result.data["outputs"][0]["text"].strip() == "10"


async def test_run_python_error(mock_run_context) -> None:
    with pytest.raises(ValueError) as exc_info:
        await run_python(mock_run_context, "print(non_existent_var)")
    assert "NameError" in str(exc_info.value)


async def test_run_python_timeout(mock_run_context) -> None:
    with pytest.raises(asyncio.TimeoutError):
        await run_python(mock_run_context, "import time; time.sleep(1)", timeout=0.1)
