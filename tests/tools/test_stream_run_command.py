import asyncio
from rune.adapters.ui.live_display import LiveDisplayManager
from rune.tools.run_command import run_command
from pydantic_ai import RunContext
from pydantic_ai.usage import Usage
from rune.core.context import SessionContext

async def test_streaming_updates(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    session = SessionContext()
    async with LiveDisplayManager() as live:
        session.live_display = live
        await run_command(
            RunContext(model="mock", usage=Usage(), deps=session, prompt=""),
            "bash -c 'echo one; sleep 0.05; echo two'",
            timeout=2,
        )
        # No assertions on console; the test passes if no exception is raised
