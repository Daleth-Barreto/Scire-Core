import base64

import httpx

from backend.graph.store import GraphStore
from backend.repos.github import GitHubAdapter, is_source_file
from backend.repos.index import RepoIndexer, chunk_file_with_lines
from backend.repos.qa import ask_repo
from tests.conftest import make_embed

TREE_JSON = {
    "tree": [
        {"path": "src/app.py", "sha": "a1", "type": "blob"},
        {"path": "src/util.py", "sha": "a2", "type": "blob"},
        {"path": "README.md", "sha": "a3", "type": "blob"},
        {"path": "node_modules/x.js", "sha": "a4", "type": "blob"},
        {"path": "assets/logo.png", "sha": "a5", "type": "blob"},
    ]
}


def _blob_response(mocker, content: str):
    response = mocker.MagicMock()
    response.json.return_value = {"content": base64.b64encode(content.encode()).decode()}
    return response


def _mock_github(mocker, *, tree=TREE_JSON):
    info = mocker.MagicMock()
    info.json.return_value = {"default_branch": "main"}
    tree_resp = mocker.MagicMock()
    tree_resp.json.return_value = tree

    def fake_get(url, headers=None, **kwargs):
        if "/git/trees/" in url:
            return tree_resp
        if "/git/blobs/" in url:
            sha = url.rsplit("/", 1)[-1]
            contents = {
                "a1": "def greet(name):\n    return f'hi {name}'\n",
                "a2": "def util():\n    return 42\n",
                "a3": "# README\nDemo project.\n",
            }
            return _blob_response(mocker, contents[sha])
        return info

    return mocker.patch.object(httpx.Client, "get", side_effect=fake_get)


def test_is_source_file_filters_directories():
    assert is_source_file("src/app.py")
    assert not is_source_file("node_modules/x.js")
    assert not is_source_file("assets/logo.png")


def test_chunk_file_with_lines():
    content = "\n".join(f"line{i}" for i in range(200))
    chunks = chunk_file_with_lines(content, max_lines=80)
    assert len(chunks) == 3
    assert chunks[1] == ("\n".join(f"line{i}" for i in range(80, 160)), 81)


def test_repo_add_ingests_subgraph(session, mocker):
    _mock_github(mocker)
    fake_provider = mocker.MagicMock()
    fake_provider.chat.return_value = "A demo repository."
    fake_embedder = mocker.MagicMock()
    fake_embedder.embed.side_effect = lambda texts: [make_embed(0) for _ in texts]

    store = GraphStore(session)
    indexer = RepoIndexer(
        store,
        GitHubAdapter(),
        provider=fake_provider,
        embedder=fake_embedder,
    )
    counts = indexer.add_repo("demo", "repo")

    assert counts["files"] == 3
    assert counts["chunks"] >= 3
    assert counts["skipped"] == 0

    repos = store.list_nodes(type="repo")
    assert len(repos) == 1
    assert repos[0].title == "demo/repo"
    assert repos[0].properties["summary"] == "A demo repository."

    files = store.list_nodes(type="file")
    assert {f.title for f in files} == {"src/app.py", "src/util.py", "README.md"}
    repo_id = repos[0].id
    assert {n.id for n in store.neighbors(repo_id)} == {f.id for f in files}
    assert store.list_nodes(type="chunk")


def test_repo_add_degrades_when_embeddings_rate_limited(session, mocker):
    _mock_github(mocker)
    fake_provider = mocker.MagicMock()
    fake_provider.chat.return_value = "A demo repository."
    fake_embedder = mocker.MagicMock()
    rate_error = httpx.HTTPStatusError(
        "429 Too Many Requests",
        request=httpx.Request("POST", "http://localhost/v1/embeddings"),
        response=mocker.MagicMock(),
    )
    fake_embedder.embed.side_effect = rate_error

    store = GraphStore(session)
    indexer = RepoIndexer(
        store,
        GitHubAdapter(),
        provider=fake_provider,
        embedder=fake_embedder,
    )
    counts = indexer.add_repo("demo", "repo")

    assert counts["files"] == 3
    assert store.list_nodes(type="repo")
    assert store.list_nodes(type="chunk")


def test_repo_add_is_idempotent(session, mocker):
    _mock_github(mocker)
    fake_provider = mocker.MagicMock()
    fake_provider.chat.return_value = "A demo repository."
    fake_embedder = mocker.MagicMock()
    fake_embedder.embed.side_effect = lambda texts: [make_embed(0) for _ in texts]

    store = GraphStore(session)
    indexer = RepoIndexer(
        store,
        GitHubAdapter(),
        provider=fake_provider,
        embedder=fake_embedder,
    )
    indexer.add_repo("demo", "repo")
    second = indexer.add_repo("demo", "repo")

    assert second["files"] == 3
    assert len(store.list_nodes(type="repo")) == 1
    assert len(store.list_nodes(type="file")) == 3
    assert len(store.list_nodes(type="chunk")) == 3


def test_repo_ask_returns_cited_answer(session, mocker):
    _mock_github(mocker)
    fake_provider = mocker.MagicMock()
    fake_provider.chat.return_value = "Uses greet(); see src/app.py:1."
    fake_embedder = mocker.MagicMock()
    fake_embedder.embed.side_effect = lambda texts: [make_embed(0) for _ in texts]

    store = GraphStore(session)
    indexer = RepoIndexer(
        store,
        GitHubAdapter(),
        provider=fake_provider,
        embedder=fake_embedder,
    )
    indexer.add_repo("demo", "repo")

    answer = ask_repo(
        store,
        "demo",
        "repo",
        "how does it greet?",
        provider=fake_provider,
        embedder=fake_embedder,
    )

    assert "src/app.py:1" in answer
    sent = fake_provider.chat.call_args.args[0]
    context = " ".join(m.content for m in sent)
    assert "--- src/app.py:1 ---" in context
    assert fake_provider.chat.call_count == 2
