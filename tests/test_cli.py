import os

import pytest
from typer.testing import CliRunner

from backend.core.config import get_settings
from backend.graph.db import session_scope
from cli.commands.search import FETCH_ADAPTERS
from cli.main import app
from tests.conftest import TEST_DB_URL, make_embed

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


def test_fulltext_prints_text_without_persist(monkeypatch):
    class FakeAdapter:
        def __init__(self) -> None:
            pass

        def fetch_fulltext(self, value: str) -> str:
            return "Attention is all you need."

    monkeypatch.setitem(FETCH_ADAPTERS, "epmc", FakeAdapter)
    result = runner.invoke(app, ["paper", "fulltext", "epmc:MED:1", "--no-persist"])
    assert result.exit_code == 0
    assert "Attention is all you need." in result.output


def test_fulltext_unavailable_reports_open_access(monkeypatch):
    class FakeAdapter:
        def __init__(self) -> None:
            pass

        def fetch_fulltext(self, value: str) -> None:
            return None

    monkeypatch.setitem(FETCH_ADAPTERS, "epmc", FakeAdapter)
    result = runner.invoke(app, ["paper", "fulltext", "epmc:MED:1", "--no-persist"])
    assert result.exit_code == 0
    assert "fulltext not available" in result.output


def test_fulltext_bad_source():
    result = runner.invoke(app, ["paper", "fulltext", "arxiv:1706.03762"])
    assert result.exit_code == 2
    assert "no fulltext endpoint" in result.output


def test_fulltext_persists_to_graph(session, mocker, monkeypatch):
    class FakeAdapter:
        def __init__(self) -> None:
            pass

        def fetch_fulltext(self, value: str) -> str:
            return "Graph neural networks generalize deep learning to graphs. " * 200

    monkeypatch.setitem(FETCH_ADAPTERS, "epmc", FakeAdapter)
    monkeypatch.setattr(
        "cli.commands.search.session_scope", lambda: session_scope(TEST_DB_URL)
    )
    fake_provider = mocker.MagicMock()
    fake_provider.chat.return_value = (
        '{"authors": ["Jane Doe"], "concepts": ["graph neural networks"], "claims": []}'
    )
    mocker.patch("backend.ingest.pipeline.get_provider", return_value=fake_provider)
    fake_embedder = mocker.MagicMock()
    fake_embedder.embed.return_value = [make_embed(0)]
    mocker.patch("backend.ingest.pipeline.get_embedder", return_value=fake_embedder)

    result = runner.invoke(app, ["paper", "fulltext", "epmc:MED:1"])
    assert result.exit_code == 0
    assert "ingested" in result.output
    assert "chunks" in result.output
