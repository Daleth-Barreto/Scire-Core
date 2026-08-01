from backend.graph.ascii import find_hub, render_tree
from backend.graph.db import session_scope
from backend.graph.json_export import export_graph, import_graph
from backend.graph.store import GraphStore
from backend.shell import repl
from tests.conftest import TEST_DB_URL


def _demo_graph(session) -> GraphStore:
    store = GraphStore(session)
    paper = store.upsert_node(type="paper", title="Transformers")
    author = store.upsert_node(type="author", title="Vaswani")
    concept = store.upsert_node(type="concept", title="Attention")
    store.upsert_edge(source_id=author.id, target_id=paper.id, type="authored_by")
    store.upsert_edge(source_id=paper.id, target_id=concept.id, type="mentions")
    session.commit()
    return store


def test_render_tree(session):
    store = _demo_graph(session)
    rendered = render_tree(store, store.list_nodes(type="paper")[0].id)
    assert "Transformers" in rendered
    assert "Attention" in rendered
    assert "[author]" in rendered


def test_find_hub(session):
    store = _demo_graph(session)
    paper = store.list_nodes(type="paper")[0]
    assert find_hub(store) == paper.id


def test_export_import_roundtrip(session):
    source = _demo_graph(session)
    data = export_graph(source)
    assert len(data["nodes"]) == 3
    assert len(data["edges"]) == 2

    target = GraphStore(session)
    counts = import_graph(target, data)
    assert counts == {"nodes": 3, "edges": 2}
    assert len(target.list_nodes()) == 3
    assert len(target.list_edges()) == 2


def test_shell_commands(session, mocker, fake_embedder):
    fake_provider = mocker.MagicMock()
    fake_provider.chat.return_value = "a reply"
    mocker.patch("backend.shell.session_scope", lambda: session_scope(TEST_DB_URL))

    from backend.memory.notes import list_notes

    output: list[str] = []
    with session_scope(TEST_DB_URL) as s:
        store = GraphStore(s)
        store.upsert_node(type="concept", title="Semantic Search Target", embedding=[0.5] * 3072)

    repl(
        ["hello world", "/note a thought", "/search semantic", "/quit"],
        provider=fake_provider,
        output=output.append,
    )

    text = "\n".join(output)
    assert "a reply" in text
    assert "Semantic Search Target" in text

    with session_scope(TEST_DB_URL) as s:
        notes = list_notes(GraphStore(s))
        assert len(notes) == 1
        assert notes[0].summary == "a thought"
        actions = [n for n in GraphStore(s).list_nodes(type="action")]
        assert any(a.title == "chat" for a in actions)
