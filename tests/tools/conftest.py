from __future__ import annotations

import pytest
from pydantic_ai import RunContext
from pydantic_ai.usage import Usage  # Import the Usage class
from rune.core.context import SessionContext

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
        deps=session_ctx
    )
