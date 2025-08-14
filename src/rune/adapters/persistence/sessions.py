from __future__ import annotations

from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, Field

from rune.core.context import SessionContext
from rune.core.messages import ModelMessage, ModelMessagesTypeAdapter


class Session(BaseModel):
    """Represents the stored state of a session."""

    messages: list[ModelMessage] = Field(default_factory=list)
    context: SessionContext = Field(default_factory=SessionContext)


# Rebuild the model to handle forward references
Session.model_rebuild()


def get_sessions_dir(base_dir: Path) -> Path:
    sessions_dir = base_dir / ".rune" / "sessions"
    sessions_dir.mkdir(exist_ok=True, parents=True)
    return sessions_dir


def save_session(path: Path, session: Session) -> None:
    path.write_bytes(session.model_dump_json(indent=2).encode("utf-8"))


def load_session(path: Path) -> Session:
    raw_data = path.read_bytes()
    try:
        # First, try to parse it as the new Session model
        return Session.model_validate_json(raw_data)
    except Exception:
        # If that fails, assume it's the old format (a list of messages)
        messages = ModelMessagesTypeAdapter.validate_json(raw_data)
        return Session(messages=messages)


def choose_session(console, base_dir: Path) -> Path | None:
    sessions_dir = get_sessions_dir(base_dir)
    sessions = sorted(
        sessions_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True
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
