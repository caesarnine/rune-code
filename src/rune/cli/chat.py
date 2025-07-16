from __future__ import annotations

import asyncio
import os
import shutil
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from typing import get_args

import typer
from prompt_toolkit import PromptSession
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.document import Document
from prompt_toolkit.history import FileHistory
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.patch_stdout import patch_stdout
from prompt_toolkit.styles import Style
from pydantic_ai import Agent, capture_run_messages
from pydantic_ai.models import KnownModelName
from pydantic_ai.usage import UsageLimits
from rich.spinner import Spinner

from rune.adapters.persistence.sessions import (
    choose_session,
    load_messages,
    save_messages,
)
from rune.adapters.ui.console import console
from rune.adapters.ui.glyphs import GLYPH, SPINNER_TEXT
from rune.adapters.ui.live_display import LiveDisplayManager
from rune.adapters.ui.render import prose
from rune.agent.factory import build_agent
from rune.cli.models import app as models_app
from rune.core.context import SessionContext
from rune.core.messages import ModelMessage, ModelRequest

RUNE_DIR = Path.cwd() / ".rune"
PROMPT_HISTORY = RUNE_DIR / "prompt.history"
SNAPSHOT_DIR = RUNE_DIR / "snapshots"


pt_style = Style.from_dict({"": "ansicyan"})


class ModelCompleter(Completer):
    """A completer for the /model slash command."""

    def __init__(self):
        self.all_models = sorted(list(get_args(KnownModelName.__value__)))

    def get_completions(
        self, document: Document, complete_event
    ) -> Iterable[Completion]:
        text = document.text_before_cursor
        words = text.split()

        # Activate only when typing the second word of "/model <...>'"
        if len(words) > 1 and words[0] == "/model":
            word_to_complete = document.get_word_before_cursor()

            for model_name in self.all_models:
                if model_name.startswith(word_to_complete):
                    yield Completion(model_name, start_position=-len(word_to_complete))


app = typer.Typer(add_completion=True, no_args_is_help=True)
app.add_typer(models_app)


async def run_agent_turn(
    agent: Agent,
    user_input: str,
    history: list[ModelMessage],
    session_ctx: SessionContext,
) -> list[ModelMessage]:
    """Handles a single turn of the agent's execution."""

    async with LiveDisplayManager() as live_display:
        session_ctx.live_display = live_display

        with capture_run_messages() as messages:
            try:
                async with agent.iter(
                    user_input,
                    message_history=history,
                    usage_limits=UsageLimits(request_limit=1000),
                    deps=session_ctx,
                ) as run:
                    async for node in run:
                        live_display.update(Spinner("dots", text=SPINNER_TEXT))

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
                                prose("thinking", thinking_txt, glyph=True)
                            if out_txt.strip():
                                prose("assistant", out_txt, glyph=True)

                    result = run.result
                return result.all_messages()

            except asyncio.CancelledError:
                console.print("\n[bold yellow]Interrupted.[/]")

                # Return a message indicating the interruption
                interrupted_message = ModelRequest.user_text_prompt("User interrupted.")
                return [*messages, interrupted_message]
            finally:
                session_ctx.live_display = None


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

    session_ctx = SessionContext()
    agent = build_agent(
        model_name=model_name,
        mcp_url=mcp_url,
        mcp_stdio=mcp_stdio,
        deps_type=SessionContext,
    )

    agent_task = None

    # Key bindings
    bindings = KeyBindings()

    @bindings.add("c-c")
    def _(event):
        if agent_task and not agent_task.done():
            agent_task.cancel()
        else:
            event.app.exit(exception=KeyboardInterrupt)

    pt_session = PromptSession(
        multiline=True,
        history=FileHistory(str(PROMPT_HISTORY)),
        auto_suggest=AutoSuggestFromHistory(),
        key_bindings=bindings,
        completer=ModelCompleter(),
    )

    console.print(
        "\n🤖  Commands: /save [name], /model [name] (tab-complete), /exit, Ctrl-C to interrupt\n"
    )

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
                break

            if not user_input.strip():
                continue

            if user_input in {"/exit", "/quit"}:
                break

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

            if user_input.startswith("/model"):
                parts = user_input.split()
                if len(parts) == 2:
                    new_model = parts[1]
                    if new_model in get_args(KnownModelName.__value__):
                        agent = build_agent(
                            model_name=new_model,
                            mcp_url=mcp_url,
                            mcp_stdio=mcp_stdio,
                            deps_type=SessionContext,
                        )
                        console.print(
                            f"✅ Model switched to [bold green]{new_model}[/bold green]"
                        )
                    else:
                        console.print(
                            f"❌ [bold red]Error:[/bold red] Model '{new_model}' is not a known model."
                        )
                else:
                    console.print(
                        "Usage: /model <model_name>. Use `rune models list` to see options."
                    )
                continue

            agent_task = asyncio.create_task(
                run_agent_turn(agent, user_input, history, session_ctx)
            )

            try:
                history = await agent_task
            except asyncio.CancelledError:
                # Task was cancelled, history is already updated by run_agent_turn
                pass

            save_messages(ses_path, history)

    console.print("\n[bold italic]bye.[/]")


@app.command(name="chat")
def chat_command(
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
