# src/rune/cli/models.py
from __future__ import annotations

from collections import defaultdict
from typing import get_args

import typer
from pydantic_ai.models import KnownModelName
from rich import box
from rich.table import Table
from rich.text import Text

from rune.adapters.ui.console import console

app = typer.Typer(
    name="models",
    help="Manage and inspect available LLM models.",
    no_args_is_help=True,
)


@app.command(name="list")
def list_models(
    provider: str = typer.Option(
        None,
        "--provider",
        "-p",
        help="Filter models by a specific provider (e.g., 'openai', 'google').",
        show_choices=True,
    ),
) -> None:
    """
    Lists all available models supported by pydantic-ai, grouped by provider.
    """
    models_by_provider = defaultdict(list)
    # Use KnownModelName.__value__ to get the underlying Literal
    for model_name in get_args(KnownModelName.__value__):
        try:
            provider_name, _ = model_name.split(":", 1)
            models_by_provider[provider_name].append(model_name)
        except ValueError:
            # Handle models that don't have a provider prefix
            models_by_provider["other"].append(model_name)
    if provider:
        providers_to_show = [provider.lower()]
    else:
        providers_to_show = sorted(models_by_provider.keys())

    for p_name in providers_to_show:
        if p_name not in models_by_provider:
            console.print(f"Provider '{p_name}' not found or has no models.")
            continue

        table = Table(
            title=f"Models for [bold cyan]{p_name}[/bold cyan]",
            show_header=True,
            header_style="bold magenta",
            box=box.MINIMAL_DOUBLE_HEAD,
            padding=(0, 1),
        )
        table.add_column("Model ID", style="dim", width=60)

        for model in sorted(models_by_provider[p_name]):
            table.add_row(Text(model, style="green"))

        console.print(table)

    # Add a special section for Azure OpenAI, as it's configured differently
    if not provider or provider.lower() == "azure":
        azure_table = Table(
            title="[bold cyan]Azure OpenAI[/bold cyan]",
            show_header=True,
            header_style="bold magenta",
            box=box.MINIMAL_DOUBLE_HEAD,
            padding=(0, 1),
        )
        azure_table.add_column("Configuration", style="dim", width=30)
        azure_table.add_column("Description", width=70)

        azure_table.add_row(
            Text("Model Format", style="green"),
            "Use the format: `azure:<your-deployment-name>`",
        )
        azure_table.add_row(
            Text("AZURE_OPENAI_API_KEY", style="green"),
            "Your Azure OpenAI API key.",
        )
        azure_table.add_row(
            Text("AZURE_OPENAI_ENDPOINT", style="green"),
            "Your Azure OpenAI resource endpoint.",
        )
        azure_table.add_row(
            Text("AZURE_OPENAI_API_VERSION", style="green"),
            "The API version for your Azure OpenAI resource.",
        )
        console.print(azure_table)
