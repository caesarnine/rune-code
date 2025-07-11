from __future__ import annotations

import asyncio
import os
import shutil
from datetime import datetime
from pathlib import Path

import typer
from prompt_toolkit import PromptSession
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.history import FileHistory
from prompt_toolkit.patch_stdout import patch_stdout
from prompt_toolkit.styles import Style
from pydantic_ai import Agent
from pydantic_ai.usage import UsageLimits

from rune.adapters.persistence.sessions import (
    choose_session,
    load_messages,
    save_messages,
)
from rune.adapters.ui.console import console
from rune.adapters.ui.glyphs import GLYPH
from rune.adapters.ui.render import prose
from rune.agent.factory import build_agent
from rune.core.messages import ModelMessage

RUNE_DIR = Path.cwd() / ".rune"
PROMPT_HISTORY = RUNE_DIR / "prompt.history"
SNAPSHOT_DIR = RUNE_DIR / "snapshots"


pt_style = Style.from_dict({"": "ansicyan"})

app = typer.Typer(add_completion=True)


# ─────────────────── Chat loop ───────────────────────────────────────
async def chat_async(
    mcp_url: str | None, mcp_stdio: bool, model_name: str | None
) -> None:
    ses_path = choose_session(console)
    if ses_path:
        history = load_messages(ses_path)
        console.print(f"📂  Resuming session: [italic]{ses_path.stem}[/]")
    else:
        ses_path = (
            RUNE_DIR / "sessions" / f"session_{datetime.now():%Y%m%d_%H%M%S}.json"
        )
        history: list[ModelMessage] = []
        console.print("🆕  Starting new session")
        RUNE_DIR.mkdir(exist_ok=True)
        SNAPSHOT_DIR.mkdir(exist_ok=True)
        save_messages(ses_path, history)

    from rune.core.context import SessionContext

    # Instantiate the context for this session
    session_ctx = SessionContext()

    # Let the agent know about the dependency type
    agent = build_agent(
        model_name=model_name,
        mcp_url=mcp_url,
        mcp_stdio=mcp_stdio,
        deps_type=SessionContext,
    )

    pt_session = PromptSession(
        multiline=True,
        history=FileHistory(str(PROMPT_HISTORY)),
        auto_suggest=AutoSuggestFromHistory(),
    )

    console.print("\n🤖  Commands: /save [name], /exit\n")

    async with agent.run_mcp_servers():
        while True:
            try:
                with patch_stdout():
                    user_input = await pt_session.prompt_async(
                        f"{GLYPH['user'][0]} ",
                        style=pt_style,
                        multiline=True,
                        prompt_continuation=f"{GLYPH['user'][0]} ",
                    )
            except (EOFError, KeyboardInterrupt):
                console.print("\n[bold italic]bye.[/]")
                break

            if not user_input.strip():
                continue
            if user_input in {"/exit", "/quit"}:
                console.print("[italic]bye.[/]")
                break

            # manual snapshot
            if user_input.startswith("/save"):
                _, *maybe = user_input.split(maxsplit=1)
                fname = (
                    maybe[0]
                    if maybe
                    else f"snapshot_{datetime.now():%Y%m%d_%H%M%S}.json"
                )
                if not fname.endswith(".json"):
                    fname += ".json"
                shutil.copy2(ses_path, SNAPSHOT_DIR / fname)
                console.print(f"💾  Snapshot saved ➜ {fname}")
                continue

            # ─── run the LLM turn ───────────────────────────────
            with console.status("[bold green]Thinking...[/]"):
                async with agent.iter(
                    user_input,
                    message_history=history,
                    usage_limits=UsageLimits(request_limit=1000),
                    deps=session_ctx,
                ) as run:
                    async for node in run:
                        if Agent.is_call_tools_node(node):
                            # print the assistant's provisional text
                            thinking_txt = "".join(
                                p.content
                                for p in node.model_response.parts
                                if p.part_kind == "thinking"
                            )
                            out_txt = "".join(
                                p.content
                                for p in node.model_response.parts
                                if p.part_kind == "text"
                            )

                            if thinking_txt.strip():
                                prose(
                                    "thinking", thinking_txt, glyph=True
                                )  # reuse UI helper
                            if out_txt.strip():
                                prose("assistant", out_txt, glyph=True)  # reuse UI helper

                    result = run.result

            # prose("assistant", result.output, glyph=True)
            history = result.all_messages()

            save_messages(ses_path, history)


@app.command()
def chat(
    mcp_url: str | None = typer.Option(
        None,
        "--mcp-url",
        help="URL of external MCP SSE server (e.g. http://localhost:3001/sse)",
    ),
    mcp_stdio: bool = typer.Option(
        False,
        "--mcp-stdio",
        help="Spawn local `mcp-run-python stdio` subprocess",
    ),
    model: str = typer.Option(
        None,
        "--model",
        help="Override the LLM model to use, e.g. 'openai:gpt-4o'",
    ),
) -> None:
    """Start or resume a chat session with a Rich tool UI."""
    model_name = model or os.getenv("RUNE_MODEL")
    asyncio.run(chat_async(mcp_url, mcp_stdio, model_name))
