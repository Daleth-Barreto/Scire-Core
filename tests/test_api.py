import httpx
import pytest
from fastapi.testclient import TestClient

from backend.api.main import app
from backend.core.envfile import mask
from backend.graph.db import session_scope
from backend.graph.store import GraphStore
from tests.conftest import TEST_DB_URL, make_embed

ATOM_XML = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>http://arxiv.org/abs/1706.03762</id>
    <published>2017-06-12</published>
    <title>Attention Is All You Need</title>
    <summary>The Transformer architecture.</summary>
    <author><name>Ashish Vaswani</name></author>
  </entry>
</feed>"""

DDG_HTML = """
<html><body><div id="links">
<div class="result">
  <a rel="nofollow" class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.org%2Ftransformers&rut=abc">Transformers Explained</a>
  <a class="result__snippet" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.org%2Ftransformers">Attention is all you need.</a>
</div>
</div></body></html>
"""


@pytest.fixture()
def client(session):
    return TestClient(app)


@pytest.fixture(autouse=True)
def _test_db(mocker):
    mocker.patch("backend.api.main.session_scope", lambda: session_scope(TEST_DB_URL))


@pytest.fixture(autouse=True)
def _clean_session_keys():
    from backend.core.config import clear_session_keys

    clear_session_keys()
    yield
    clear_session_keys()


def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok"}


def test_graph_dump_and_node_detail(client, session):
    with session_scope(TEST_DB_URL) as s:
        store = GraphStore(s)
        paper = store.upsert_node(type="paper", title="Transformers")
        author = store.upsert_node(type="author", title="Vaswani")
        store.upsert_edge(source_id=author.id, target_id=paper.id, type="authored_by")

    graph = client.get("/api/graph").json()
    assert len(graph["nodes"]) == 2
    assert len(graph["edges"]) == 1
    assert all("embedding" not in n for n in graph["nodes"])

    detail = client.get(f"/api/graph/nodes/{paper.id}").json()
    assert detail["title"] == "Transformers"
    assert {n["title"] for n in detail["neighbors"]} == {"Vaswani"}

    assert client.get("/api/graph/nodes/missing").status_code == 404


def test_graph_search(client, session, mocker):
    with session_scope(TEST_DB_URL) as s:
        GraphStore(s).upsert_node(type="concept", title="Attention", embedding=make_embed(0))
    fake_embedder = mocker.MagicMock()
    fake_embedder.embed.return_value = [make_embed(0)]
    mocker.patch("backend.core.providers.get_embedder", return_value=fake_embedder)

    results = client.get("/api/graph/search", params={"q": "attention"}).json()
    assert results and results[0]["title"] == "Attention"
    assert "distance" in results[0]


def test_search_web_academic(client, mocker):
    from backend.search.arxiv import ArxivAdapter
    from backend.search.duckduckgo import DuckDuckGoAdapter

    arxiv_response = mocker.MagicMock()
    arxiv_response.text = ATOM_XML
    ddg_response = mocker.MagicMock()
    ddg_response.text = DDG_HTML
    ss_response = mocker.MagicMock()
    ss_response.json.return_value = {"data": []}

    def fake_get(url, **kwargs):
        if url.startswith(ArxivAdapter.BASE_URL):
            return arxiv_response
        if url.startswith(DuckDuckGoAdapter.SEARCH_URL):
            return ddg_response
        return ss_response

    mocker.patch.object(httpx.Client, "get", side_effect=fake_get)

    candidates = client.post("/api/search", json={"query": "transformers", "limit": 5}).json()
    sources = {c["source"] for c in candidates}
    assert "arxiv" in sources
    assert "web" in sources


def test_notes_roundtrip(client):
    created = client.post("/api/notes", json={"content": "a thought"}).json()
    notes = client.get("/api/notes").json()
    assert any(n["id"] == created["id"] for n in notes)


def test_config_masks_keys(client, mocker):
    from pydantic import SecretStr

    from backend.core.config import get_settings

    settings = get_settings()
    raw = "sk-test-secret-value"
    mocker.patch.object(settings, "llm_provider", "openai")
    mocker.patch.object(settings, "openai_api_key", SecretStr(raw))

    data = client.get("/api/config").json()
    assert data["provider"] == "openai"
    assert data["api_key"] == mask(raw)
    assert raw not in data["api_key"]
    assert "api_key" in data


def _deterministic_settings(mocker):
    """Force provider=openai with empty env keys so masking tests are hermetic."""
    from pydantic import SecretStr

    from backend.core.config import get_settings

    settings = get_settings()
    mocker.patch.object(settings, "llm_provider", "openai")
    mocker.patch.object(settings, "openai_api_key", SecretStr(""))
    mocker.patch.object(settings, "github_token", SecretStr(""))
    return settings


def test_config_keys_write_creates_encrypted_file(client, tmp_path, monkeypatch, mocker):
    _deterministic_settings(mocker)
    monkeypatch.setenv("SCIRE_KEYS_PATH", str(tmp_path / "keys.enc"))

    resp = client.post(
        "/api/config/keys",
        json={"passphrase": "p4ss", "keys": {"OPENAI_API_KEY": "sk-123"}},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "saved"

    enc_path = tmp_path / "keys.enc"
    assert enc_path.exists()
    assert b"sk-123" not in enc_path.read_bytes()

    data = client.get("/api/config").json()
    assert data["encrypted"] is True
    assert data["api_key"] == mask("sk-123")


def test_config_unlock_roundtrip(client, tmp_path, monkeypatch, mocker):
    from backend.core.config import clear_session_keys

    _deterministic_settings(mocker)
    monkeypatch.setenv("SCIRE_KEYS_PATH", str(tmp_path / "keys.enc"))
    client.post(
        "/api/config/keys",
        json={"passphrase": "p4ss", "keys": {"OPENAI_API_KEY": "sk-123"}},
    )
    clear_session_keys()

    assert client.get("/api/config").json()["api_key"] == "(unset)"

    resp = client.post("/api/config/unlock", json={"passphrase": "p4ss"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "unlocked"

    data = client.get("/api/config").json()
    assert data["api_key"] == mask("sk-123")

    bad = client.post("/api/config/unlock", json={"passphrase": "wrong"})
    assert bad.status_code == 401

    client.post("/api/config/lock")
    assert client.get("/api/config").json()["api_key"] == "(unset)"


def test_config_keys_never_returned(client, tmp_path, monkeypatch, mocker):
    _deterministic_settings(mocker)
    monkeypatch.setenv("SCIRE_KEYS_PATH", str(tmp_path / "keys.enc"))
    client.post(
        "/api/config/keys",
        json={
            "passphrase": "p4ss",
            "keys": {"OPENAI_API_KEY": "sk-123", "GITHUB_TOKEN": "ghp_secret"},
        },
    )

    for resp in (
        client.get("/api/config"),
        client.post("/api/config/unlock", json={"passphrase": "p4ss"}),
    ):
        assert "sk-123" not in resp.text
        assert "ghp_secret" not in resp.text


def test_ingest_pdf_endpoint(client, mocker, tmp_path):
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate

    path = tmp_path / "survey.pdf"
    style = getSampleStyleSheet()["Normal"]
    doc = SimpleDocTemplate(str(path), pagesize=letter)
    doc.build(
        [
            Paragraph("Graph Neural Networks", style),
            Paragraph("Message passing generalizes.", style),
        ]
    )

    fake_provider = mocker.MagicMock()
    fake_provider.chat.return_value = (
        '{"authors": ["Jane Doe"], "concepts": ["message passing"], "claims": []}'
    )
    fake_embedder = mocker.MagicMock()
    fake_embedder.embed.side_effect = lambda texts: [
        make_embed(i % 3072) for i in range(len(texts))
    ]
    mocker.patch("backend.ingest.pipeline.get_provider", return_value=fake_provider)
    mocker.patch("backend.ingest.pipeline.get_embedder", return_value=fake_embedder)

    with open(path, "rb") as fh:
        response = client.post(
            "/api/ingest/pdf",
            files={"file": ("survey.pdf", fh, "application/pdf")},
            data={"title": "GNN Survey"},
        )
    assert response.status_code == 200, response.text
    counts = response.json()
    assert counts["paper_id"]
    assert counts["chunks"] >= 1

    with session_scope(TEST_DB_URL) as s:
        store = GraphStore(s)
        papers = store.list_nodes(type="paper")
        assert any(p.title == "GNN Survey" for p in papers)
        assert store.list_nodes(type="author")
        assert store.list_nodes(type="action")

    bad = client.post("/api/ingest/pdf", files={"file": ("notes.txt", b"x", "text/plain")})
    assert bad.status_code == 400


def test_paper_fetch_persists(client, mocker):
    arxiv_response = mocker.MagicMock()
    arxiv_response.text = ATOM_XML
    mocker.patch.object(httpx.Client, "get", return_value=arxiv_response)

    paper = client.post("/api/papers/fetch", json={"external_id": "arxiv:1706.03762"}).json()
    assert paper["source"] == "arxiv"
    assert paper["title"] == "Attention Is All You Need"

    with session_scope(TEST_DB_URL) as s:
        store = GraphStore(s)
        assert any(p.title == "Attention Is All You Need" for p in store.list_nodes(type="paper"))
        assert any(a.title == "fetch" for a in store.list_nodes(type="action"))

    bad = client.post("/api/papers/fetch", json={"external_id": "bogus"}).json()
    assert "detail" in bad
    assert client.post("/api/papers/fetch", json={"external_id": "bogus"}).status_code == 400


def test_chat_logs_action_and_replies(client, mocker):
    fake_provider = mocker.MagicMock()
    fake_provider.chat.return_value = "hi there"
    mocker.patch("backend.core.providers.get_provider", return_value=fake_provider)

    reply = client.post("/api/chat", json={"message": "hello"}).json()
    assert reply["answer"] == "hi there"

    with session_scope(TEST_DB_URL) as s:
        actions = GraphStore(s).list_nodes(type="action")
    assert any(a.title == "chat" for a in actions)
