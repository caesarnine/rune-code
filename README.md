# Rune – Terminal-first AI Coding Assistant

Rune is a flexible, local AI coding agent.

It brings an LLM into your own terminal, augments it with safe “power-tools” (grep, diff-edit, Python kernel, shell commands, TODO management, etc.) and renders everything with Rich for a pleasant TUI experience.

---

## Table of contents
1. [Features](#features)
2. [Quick start](#quick-start)
3. [Usage cheatsheet](#usage-cheatsheet)
4. [Architecture overview](#architecture-overview)
5. [Core libraries](#core-libraries)
6. [Testing & linting](#testing--linting)
7. [Contributing](#contributing)
8. [License](#license)

---

## Features

| Capability                               | Notes |
|------------------------------------------|-------|
| **Interactive chat CLI**                 | Multi-line editing, history & `/save` snapshots via *prompt-toolkit*. |
| **LLM orchestration**                    | Powered by **pydantic-ai** with multi-tool reasoning and optional MCP back-ends. |
| **Rich tool ecosystem**                  | Edit files with fuzzy diffs, grep the codebase, run shell or stateful Python, fetch URLs, manage TODOs and more. |
| **Colourful TUI output**                 | Glyph bars, syntax-highlighted diffs, tables & panels – all via **Rich**. |
| **Persistent sessions**                  | Last five conversations saved under `.rune/sessions/…` for instant resumption. |
| **First-class TODO list**                | Tasks tracked in-memory per session; rendered as pulsing-dot list. |
| **Path sandboxing**                      | All filesystem tools refuse to operate outside the current working directory. |
| **Extensible**                           | Drop a new function under `src/rune/tools/`, decorate with `@register_tool`, and it is auto-wired into the agent. |

---

## Quick start

```bash
# 1. Clone & install
git clone https://github.com/caesarnine/rune.git
cd rune
uv sync --all-extras
uv venv

# 2. Run the CLI
rune                          # starts the chat loop
````

Environment variables

```bash
export RUNE_MODEL="openai:gpt-4o"      # optional – override default model
```

---

## Usage cheatsheet

| Action                              | How                                                          |
| ----------------------------------- | ------------------------------------------------------------ |
| Start a new chat                    | `rune` (choose “Start new session”)                          |
| Resume a previous session           | `rune` and pick from the list                                |
| Save a snapshot                     | Type `/save` or `/save custom_name.json`                     |
| Exit                                | `/exit` or Ctrl-D                                            |
| Change directory for shell commands | `run_command("cd path/to/dir")`                              |
| List tasks                          | `list_todos()` (the agent often calls this automatically)    |
| Run tests                           | Tell Rune: *“run the tests”* – it will call `pytest` for you |

---

## Architecture overview

```mermaid
flowchart TD
    subgraph CLI
        A["chat.py\nprompt-toolkit"]
    end
    subgraph Agent
        B["pydantic_ai.Agent"] --> C["rich_tool wrapper"]
    end
    subgraph Tools
        D["edit_file\nrun_python\ngrep\n…"]
    end
    subgraph UI
        E["render.py\nRich console"]
    end
    subgraph Persistence
        F[".rune/sessions/*.json"]
    end

    A -->|prompt| B
    B -->|XML tool call| C
    C -->|exec| D
    D -->|ToolResult| C
    C -->|renderable| E
    B -->|assistant text| E
    A <--> F
```

### Execution sequence

```mermaid
sequenceDiagram
    participant U as User
    participant P as CLI Prompt
    participant G as Agent
    participant W as Tool Wrapper
    participant T as Tool
    participant R as Rich UI

    U->>P: type message
    P->>G: agent.iter(...)
    loop stream
        G-->>W: <tool call>
        W->>R: display_tool_call()
        W->>T: execute
        T-->>W: ToolResult
        W->>R: display_tool_result()
        W-->>G: <tool_result>
    end
    G-->>P: assistant reply
    P->>R: render text
```

---

## Core libraries

| Domain                | Library                          |
| --------------------- | -------------------------------- |
| LLM orchestration     | **pydantic-ai**                  |
| Terminal UI           | **Rich**                         |
| CLI framework         | **Typer** + *prompt-toolkit*     |
| Diff/patch engine     | Custom `DiffApplyer` + `difflib` |
| HTTP fetch & markdown | `httpx`, `html-to-markdown`      |
| Interactive Python    | `jupyter_client`, `ipykernel`    |
| Git-style ignores     | `pathspec`                       |
| Quality tooling       | `pytest`, `ruff`, `mypy`         |

---

## Testing & linting

```bash
# Run all unit tests (tool layer)
pytest

# Static typing (Python ≥3.10)
mypy src

# Lint & format
ruff check .
ruff format .
```

Tests live under `tests/tools/` and cover success paths and edge-cases for every tool.

---

## Contributing

1. Fork and create a feature branch.
2. Follow the style conventions enforced by `ruff`.
3. Add unit tests for new tools or behaviour.
4. Ensure `pytest`, `ruff check`, and `mypy` all pass.
5. Submit a PR.

---

## License

Rune is licensed under the **Apache 2.0**
