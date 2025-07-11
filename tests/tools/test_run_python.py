from __future__ import annotations

import pytest

from rune.tools.run_python import run_python

import asyncio

def test_run_python_simple() -> None:
    result = run_python("print('hello')")
    assert result.status == "success"
    assert len(result.data["outputs"]) >= 1
    assert result.data["outputs"][0]["text"] == "hello"


def test_run_python_variable() -> None:
    run_python("x = 10")
    result = run_python("print(x)")
    assert result.status == "success"
    assert len(result.data["outputs"]) >= 1
    assert result.data["outputs"][0]["text"] == "10"


def test_run_python_error() -> None:
    with pytest.raises(ValueError) as exc_info:
        run_python("print(non_existent_var)")
    assert "NameError" in str(exc_info.value)


def test_run_python_timeout() -> None:
    with pytest.raises(TimeoutError):
        run_python("import time; time.sleep(0.2)", timeout=0.1)
