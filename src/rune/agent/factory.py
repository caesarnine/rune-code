from __future__ import annotations

import importlib
import os
import pkgutil
from importlib import resources

from pydantic_ai import Agent
from pydantic_ai.mcp import MCPServerSSE, MCPServerStdio
from pydantic_ai.models.openai import OpenAIModel, OpenAIResponsesModel
from pydantic_ai.providers.azure import AzureProvider

import rune.tools as _pkg
from rune.agent.rich_wrappers import rich_tool
from rune.core.context import RuneDependencies
from rune.core.model_settings import build_settings
from rune.tools.edit_file import edit_file
from rune.tools.fetch_url import fetch_url
from rune.tools.get_metadata import get_metadata
from rune.tools.grep import grep
from rune.tools.list_files import list_files
from rune.tools.read_chunk import read_chunk
from rune.tools.read_file import read_file
from rune.tools.run_command import run_command
from rune.tools.run_python import run_python
from rune.tools.todos import add_todos, list_todos, update_todos
from rune.tools.write_file import write_file

DEFAULT_MODEL = "google-vertex:gemini-2.5-pro"


def _load_system_prompt() -> str:
    # Reads ai_chat/core/prompts/system_prompt.md at runtime
    return resources.files("rune.core.prompts").joinpath("system_prompt.md").read_text()


def _build_mcp_servers(mcp_url: str | None, mcp_stdio: bool) -> list:
    mcp_servers = []
    if mcp_url:
        mcp_servers.append(MCPServerSSE(url=mcp_url))
    if mcp_stdio:
        mcp_servers.append(
            MCPServerStdio(
                "deno",
                args=[
                    "run",
                    "-N",
                    "-R=node_modules",
                    "-W=node_modules",
                    "--node-modules-dir=auto",
                    "jsr:@pydantic/mcp-run-python",
                    "stdio",
                ],
            )
        )
    return mcp_servers


def build_agent(
    *,
    model_name: str | None = None,
    model_overrides: dict | None = None,
    mcp_url: str | None = None,
    mcp_stdio: bool = False,
) -> Agent:
    model_name = model_name or DEFAULT_MODEL
    settings = build_settings(model_name, model_overrides)
    model: str | OpenAIModel | OpenAIResponsesModel

    if model_name.startswith("azure:"):
        deployment = model_name.split(":", 1)[1]
        try:
            provider = AzureProvider(
                api_key=os.environ["AZURE_OPENAI_API_KEY"],
                azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
                api_version=os.environ["AZURE_OPENAI_API_VERSION"],
            )
            model = OpenAIResponsesModel(
                model=deployment, provider=provider, settings=settings
            )
        except KeyError as e:
            raise ValueError(
                f"Missing Azure environment variable: {e}. Please set AZURE_OPENAI_API_KEY, AZURE_OPENAI_ENDPOINT, and AZURE_OPENAI_API_VERSION."
            ) from e
    elif model_name.startswith("openai:"):
        model = OpenAIResponsesModel(model=model_name, settings=settings)
    else:
        model = model_name

    agent = Agent(
        system_prompt=_load_system_prompt(),
        model=model,
        model_settings=settings,
        mcp_servers=_build_mcp_servers(mcp_url, mcp_stdio),
        output_retries=10,
        deps_type=RuneDependencies,
    )

    # Register tools
    agent.tool_plain(rich_tool(edit_file))
    agent.tool_plain(rich_tool(fetch_url))
    agent.tool_plain(rich_tool(get_metadata))
    agent.tool_plain(rich_tool(grep))
    agent.tool_plain(rich_tool(list_files))
    agent.tool_plain(rich_tool(read_chunk))
    agent.tool_plain(rich_tool(read_file))
    agent.tool(rich_tool(run_command))
    agent.tool(rich_tool(run_python))
    agent.tool(rich_tool(add_todos))
    agent.tool(rich_tool(update_todos))
    agent.tool(rich_tool(list_todos))
    agent.tool_plain(rich_tool(write_file))

    return agent
