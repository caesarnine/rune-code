# tests/cli/test_models.py
from __future__ import annotations

from typer.testing import CliRunner

from rune.cli.chat import app

runner = CliRunner()


def test_list_models_all():
    result = runner.invoke(app, ["models", "list"])
    assert result.exit_code == 0
    assert "openai" in result.stdout
    assert "google" in result.stdout
    assert "anthropic" in result.stdout
    assert "gpt-4o" in result.stdout


def test_list_models_provider_filter():
    result = runner.invoke(app, ["models", "list", "--provider", "openai"])
    assert result.exit_code == 0
    assert "openai" in result.stdout
    assert "google" not in result.stdout
    assert "gpt-4o" in result.stdout


def test_list_models_provider_not_found():
    result = runner.invoke(app, ["models", "list", "--provider", "nonexistent"])
    assert result.exit_code == 0
    assert "Provider 'nonexistent' not found" in result.stdout
