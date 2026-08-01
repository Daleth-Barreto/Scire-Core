import os

import pytest
from typer.testing import CliRunner

from backend.core.config import get_settings
from cli.main import app

runner = CliRunner()


def test_whoami_reports_provider_and_key_status(monkeypatch):
    class FakeSettings:
        llm_provider = "openrouter"

        @property
        def provider_api_key(self):
            raise ValueError("no key")

    monkeypatch.setattr("cli.main.get_settings", lambda: FakeSettings())
    result = runner.invoke(app, ["whoami"])
    assert result.exit_code == 0
    assert "provider: openrouter" in result.output
    assert "api key: missing" in result.output


def test_chat_without_key_prints_error_and_exits(monkeypatch):
    def no_provider(*args, **kwargs):
        raise ValueError("API key for provider 'openrouter' is not set")

    monkeypatch.setattr("backend.core.providers.get_provider", no_provider)
    result = runner.invoke(app, ["chat", "hola"])
    assert result.exit_code == 1
    assert "API key" in result.output


def test_chat_returns_reply(monkeypatch):
    class FakeProvider:
        def chat(self, messages, model=None):
            return "hola humano"

    monkeypatch.setattr("backend.core.providers.get_provider", lambda: FakeProvider())
    result = runner.invoke(app, ["chat", "hola"])
    assert result.exit_code == 0
    assert result.output.strip() == "hola humano"


def test_smoke_real_llm_call():
    if os.environ.get("SCIRE_CI") == "1":
        raise pytest.skip("no real LLM call in CI")
    try:
        _key = get_settings().provider_api_key
    except ValueError:
        raise pytest.skip("no API key configured; real call skipped")
    result = runner.invoke(app, ["chat", "say: ok"])
    assert result.exit_code == 0
    assert result.output.strip()
