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
    Session,
    choose_session,
    get_sessions_dir,
    load_session,
    save_session,
)
from rune.adapters.ui.console import console
from rune.adapters.ui.glyphs import GLYPH, SPINNER_TEXT
from rune.adapters.ui.live_display import LiveDisplayManager
from rune.adapters.ui.render import prose
from rune.agent.factory import build_agent
from rune.cli.models import app as models_app
from rune.core.context import SessionContext
from rune.core.messages import ModelMessage, ModelRequest

# Compute rune directories at runtime based on chat startup directory
RUNE_DIR: Path | None = None
PROMPT_HISTORY: Path | None = None
SNAPSHOT_DIR: Path | None = None


pt_style = Style.from_dict({"": "ansicyan"})


class ModelCompleter(Completer):
    """A completer for the /model slash command."""

    def __init__(self):
        all_models = get_args(KnownModelName.__value__)
        providers = {m.split(":")[0] for m in all_models}
        self.providers = sorted(list(providers | {"azure"}))
        self.all_models = sorted(list(all_models))

    def get_completions(
        self, document: Document, complete_event
    ) -> Iterable[Completion]:
        text = document.text_before_cursor.lstrip()
        if not text.startswith("/model "):
            return

        word_to_complete = document.get_word_before_cursor()
        current_model_text = text.split(" ")[1] if len(text.split(" ")) > 1 else ""

        if ":" not in current_model_text:
            # User is typing the provider
            for provider in self.providers:
                if provider.startswith(word_to_complete):
                    yield Completion(
                        f"{provider}:",
                        start_position=-len(word_to_complete),
                        display=provider,
                    )
        else:
            # User is typing the model name
            for model_name in self.all_models:
                if model_name.startswith(current_model_text):
                    yield Completion(
                        model_name,
                        start_position=-len(current_model_text),
                    )


app = typer.Typer(add_completion=True, invoke_without_command=True)
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
    base_dir = Path.cwd()
    ses_path = choose_session(console, base_dir)
    if ses_path:
        session = load_session(ses_path)
        console.print(f"📂  Resuming session: [italic]{ses_path.stem}[/]")
    else:
        ses_path = base_dir / ".rune" / "sessions" / f"session_{datetime.now():%Y%m%d_%H%M%S}.json"
        session = Session()
        console.print("🆕  Starting new session")
        (base_dir / ".rune" / "sessions").mkdir(parents=True, exist_ok=True)
        (base_dir / ".rune" / "snapshots").mkdir(parents=True, exist_ok=True)
        save_session(ses_path, session)

    session_ctx = session.context
    session_ctx.current_working_dir = base_dir
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
        history=FileHistory(str(base_dir / ".rune" / "prompt.history")),
        auto_suggest=AutoSuggestFromHistory(),
        key_bindings=bindings,
        completer=ModelCompleter(),
    )

    console.print(
        "\n🤖  Commands: /save [name], /model [name] (tab-complete), /exit, Ctrl-C to interrupt"
    )
    console.print(
        "💡  To submit, press [bold]Esc+Enter[/], [bold]Option+Enter[/] (Mac), or [bold]Alt+Enter[/] (Windows).\n"
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
                snapshot_dir = base_dir / ".rune" / "snapshots"
                snapshot_dir.mkdir(parents=True, exist_ok=True)
                shutil.copy2(ses_path, snapshot_dir / fname)
                console.print(f"💾  Snapshot saved ➜ {fname}")
                continue

            if user_input.startswith("/model"):
                parts = user_input.split()
                if len(parts) == 2:
                    new_model = parts[1]
                    try:
                        agent = build_agent(
                            model_name=new_model,
                            mcp_url=mcp_url,
                            mcp_stdio=mcp_stdio,
                            deps_type=SessionContext,
                        )
                        console.print(
                            f"✅ Model switched to [bold green]{new_model}[/bold green]"
                        )
                    except ValueError as e:
                        console.print(f"❌ [bold red]Error:[/bold red] {e}")
                else:
                    console.print(
                        "Usage: /model <model_name>. Use `rune models list` to see options."
                    )
                continue

            agent_task = asyncio.create_task(
                run_agent_turn(agent, user_input, session.messages, session_ctx)
            )

            try:
                session.messages = await agent_task
            except asyncio.CancelledError:
                # Task was cancelled, history is already updated by run_agent_turn
                pass

            save_session(ses_path, session)

    console.print("\n[bold italic]bye.[/]")


@app.callback()
def main(
    ctx: typer.Context,
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
    """Rune: An interactive AI coding agent."""
    if ctx.invoked_subcommand is None:
        model_name = model or os.getenv("RUNE_MODEL")
        asyncio.run(chat_async(mcp_url, mcp_stdio, model_name))
