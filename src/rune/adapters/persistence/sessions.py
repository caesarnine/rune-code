from __future__ import annotations

from datetime import datetime
from pathlib import Path

from pydantic_core import to_json

from rune.core.messages import ModelMessage, ModelMessagesTypeAdapter

SESSIONS_DIR = Path.cwd() / ".rune" / "sessions"
SESSIONS_DIR.mkdir(exist_ok=True, parents=True)


def save_messages(path: Path, msgs: list[ModelMessage]) -> None:
    path.write_bytes(to_json(msgs))


def load_messages(path: Path) -> list[ModelMessage]:
    return ModelMessagesTypeAdapter.validate_json(path.read_bytes())


def choose_session(console) -> Path | None:
    sessions = sorted(
        SESSIONS_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True
    )[:5]
    if not sessions:
        return None
    console.print("[bold]🗂  Previous sessions:[/bold]")
    for idx, p in enumerate(sessions, 1):
        ts = datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
        console.print(f"  {idx}. {p.stem:<25} (last used {ts})")
    console.print(f"  {len(sessions) + 1}. Start new session")
    while True:
        import typer

        choice = typer.prompt("Select", default=str(len(sessions) + 1))
        if choice.isdigit():
            i = int(choice)
            if 1 <= i <= len(sessions):
                return sessions[i - 1]
            if i == len(sessions) + 1:
                return None
