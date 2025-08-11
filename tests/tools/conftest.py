from __future__ import annotations

import pytest
from pydantic_ai import RunContext
from pydantic_ai.usage import Usage  # Import the Usage class
from rune.core.context import SessionContext

@pytest.fixture(autouse=True)
def cleanup_kernel():
    """
    This autouse fixture ensures that the kernel is shut down after every test
    that uses it. This prevents state from leaking between tests.
    """
    yield
    # This code runs after each test completes
    from rune.tools import run_python

    if run_python._kernel_manager:
        if run_python._kernel_manager.is_alive():
            run_python._kernel_manager.shutdown_kernel()
        run_python._kernel_manager = None
        run_python._kernel_client = None


@pytest.fixture
def mock_run_context() -> RunContext[SessionContext]:
    """
    Creates a mock RunContext for tools that require it.
    """
    session_ctx = SessionContext()
    # Provide all required arguments for the RunContext constructor.
    # The tests only need `deps`, so the others can be dummy values.
    return RunContext(
        model="mock-model",
        usage=Usage(),  # A default, empty Usage object
        prompt="",      # An empty string for the prompt
        deps=session_ctx,
    )
