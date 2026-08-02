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


def test_audit_prints_verdicts(session, mocker, monkeypatch):
    import json

    from backend.graph.store import GraphStore

    store = GraphStore(session)
    paper = store.upsert_node(type="paper", title="Attention Paper", embedding=make_embed(1))
    claim = store.upsert_node(
        type="claim", title="Attention scales as QK^T", embedding=make_embed(0)
    )
    store.upsert_edge(source_id=paper.id, target_id=claim.id, type="mentions")
    repo = store.upsert_node(type="repo", title="demo/repo")
    store.upsert_node(
        type="chunk",
        title="src/app.py",
        summary="def attention(): pass",
        embedding=make_embed(0),
        properties={"repo": repo.id, "path": "src/app.py", "start_line": 10},
    )
    session.commit()

    monkeypatch.setattr(
        "cli.commands.audit.session_scope", lambda: session_scope(TEST_DB_URL)
    )
    fake_provider = mocker.MagicMock()
    fake_provider.chat.return_value = json.dumps(
        {"verdict": "supported", "evidence": "src/app.py:10", "reason": "found"}
    )
    mocker.patch("backend.repos.audit.get_provider", return_value=fake_provider)
    fake_embedder = mocker.MagicMock()
    fake_embedder.embed.side_effect = lambda texts: [make_embed(0) for _ in texts]
    mocker.patch("backend.repos.audit.get_embedder", return_value=fake_embedder)

    result = runner.invoke(app, ["audit", "Attention Paper", "demo/repo"])
    assert result.exit_code == 0
    assert "1 supported" in result.output
    assert "[OK] Attention scales as QK^T" in result.output
    assert "src/app.py:10" in result.output


def test_audit_bad_repo_format():
    result = runner.invoke(app, ["audit", "Some Paper", "norepo"])
    assert result.exit_code == 2
    assert "owner/name" in result.output


def test_deepresearch_prints_brief_and_verdict(mocker, monkeypatch, tmp_path):
    import json

    from backend.research.deepresearch import SourceNote

    fake_provider = mocker.MagicMock()
    fake_provider.chat.side_effect = [
        json.dumps(
            {
                "sections": [{"heading": "Approach", "points": ["RAG couples retrieval with generation"]}],
                "conflicts": [],
                "gaps": [],
            }
        ),
        "## RAG\n\nRAG augments LLMs [1].",
        json.dumps({"verified": True, "issues": []}),
    ]
    mocker.patch("backend.research.deepresearch.get_provider", return_value=fake_provider)
    mocker.patch(
        "backend.research.deepresearch.gather_sources",
        return_value=[
            SourceNote(
                title="RAG Paper",
                url="https://arxiv.org/abs/2005.11401",
                source="arxiv",
            )
        ],
    )

    out = tmp_path / "brief.md"
    result = runner.invoke(app, ["deepresearch", "rag", "--save", str(out)])
    assert result.exit_code == 0
    assert "## RAG" in result.output
    assert "RAG augments LLMs [1]." in result.output
    assert "verdict: verified" in result.output
    assert "RAG Paper" in result.output
    assert out.exists()


def test_deepresearch_no_sources_prints_error(mocker):
    mocker.patch("backend.research.deepresearch.gather_sources", return_value=[])
    result = runner.invoke(app, ["deepresearch", "rag"])
    assert result.exit_code == 2
    assert "no sources found" in result.output


def test_init_prints_summary(mocker, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    mocker.patch("backend.setup.init._ensure_database", return_value=("created", "created", "created"))
    mocker.patch("backend.setup.init._create_tables")
    mocker.patch("backend.setup.init._graph_ready", return_value=True)
    (tmp_path / ".env.example").write_text("LLM_PROVIDER=openrouter\n", encoding="utf-8")

    result = runner.invoke(app, ["init", "--admin-url", "postgresql+psycopg://postgres:pw@localhost:5432/postgres"], prog_name="scire")
    assert result.exit_code == 0
    assert ".env created" in result.output
    assert "database role: created" in result.output
    assert "tables ready" in result.output


def test_rank_prints_scored_papers(session, mocker, monkeypatch):
    from backend.graph.store import GraphStore

    store = GraphStore(session)
    node = store.upsert_node(
        type="paper",
        title="Attention Is All You Need",
        embedding=make_embed(0),
        properties={"source": "arxiv", "external_id": "T:attention", "cited_by_count": 100},
    )
    session.commit()

    monkeypatch.setattr(
        "cli.commands.rank.session_scope", lambda: session_scope(TEST_DB_URL)
    )
    fake_embedder = mocker.MagicMock()
    fake_embedder.embed.return_value = [make_embed(0)]
    mocker.patch("cli.commands.rank.get_embedder", return_value=fake_embedder)

    result = runner.invoke(app, ["rank", "attention"])
    assert result.exit_code == 0
    assert "Attention Is All You Need" in result.output
    assert node.id


def test_rank_no_embedder_prints_error(monkeypatch):
    def no_embedder(*args, **kwargs):
        raise ValueError("embedding model not configured")

    monkeypatch.setattr("cli.commands.rank.get_embedder", no_embedder)
    result = runner.invoke(app, ["rank", "attention"])
    assert result.exit_code == 2
    assert "cannot embed query" in result.output


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
