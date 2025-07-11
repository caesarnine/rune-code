from __future__ import annotations

import importlib
import pkgutil
from importlib import resources
from typing import Optional

from pydantic_ai import Agent, RunContext
from pydantic_ai.mcp import MCPServerSSE, MCPServerStdio
from pydantic_ai.usage import UsageLimits

import rune.tools as _pkg
from rune.agent.rich_wrappers import rich_tool
from rune.core.model_settings import build_settings
from rune.tools.registry import REGISTRY

DEFAULT_MODEL = "google-vertex:gemini-2.5-pro"


def _load_system_prompt() -> str:
    # Reads ai_chat/core/prompts/system_prompt.md at runtime
    return resources.files("rune.core.prompts").joinpath("system_prompt.md").read_text()


def _import_all_tools():
    """Ensure every module under ai_chat.tools is imported once."""
    for mod in pkgutil.walk_packages(_pkg.__path__, _pkg.__name__ + "."):
        importlib.import_module(mod.name)


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


from typing import Type


def build_agent(
    *,
    model_name: str | None = None,
    model_overrides: dict | None = None,
    mcp_url: str | None = None,
    mcp_stdio: bool = False,
    deps_type: type | None = None,
) -> Agent:
    model_name = model_name or DEFAULT_MODEL
    settings = build_settings(model_name, model_overrides)

    agent = Agent(
        system_prompt=_load_system_prompt(),
        model=model_name,
        model_settings=settings,
        mcp_servers=_build_mcp_servers(mcp_url, mcp_stdio),
        retries=10,
        deps_type=deps_type,
    )

    _import_all_tools()

    for spec in REGISTRY:
        if spec.needs_ctx:
            agent.tool(rich_tool(spec.fn))  # expects RunContext
        else:
            agent.tool_plain(rich_tool(spec.fn))  # plain callable

    return agent
