from __future__ import annotations

import pytest

from rune.tools.run_python import run_python

import asyncio

async def test_run_python_simple() -> None:
    result = await run_python("print('hello')")
    assert result.status == "success"
    assert len(result.data["outputs"]) >= 1
    assert result.data["outputs"][0]["text"].strip() == "hello"


async def test_run_python_variable() -> None:
    await run_python("x = 10")
    result = await run_python("print(x)")
    assert result.status == "success"
    assert len(result.data["outputs"]) >= 1
    assert result.data["outputs"][0]["text"].strip() == "10"


async def test_run_python_error() -> None:
    with pytest.raises(ValueError) as exc_info:
        await run_python("print(non_existent_var)")
    assert "NameError" in str(exc_info.value)


async def test_run_python_timeout() -> None:
    with pytest.raises(asyncio.TimeoutError):
        await run_python("import time; time.sleep(1)", timeout=0.1)
