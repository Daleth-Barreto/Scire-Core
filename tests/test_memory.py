from backend.graph.store import GraphStore
from backend.memory.actions import list_actions, log_action
from backend.memory.gaps import detect_gaps
from backend.memory.notes import add_note, list_notes
from tests.conftest import make_embed


def test_note_persisted_tied_to_context(session, mocker):
    store = GraphStore(session)
    paper = store.upsert_node(type="paper", title="Some Paper")
    session.commit()

    fake_embedder = mocker.MagicMock()
    fake_embedder.embed.return_value = [make_embed(0)]
    note = add_note(
        store, "Transformer attention matters", context_id=paper.id, embedder=fake_embedder
    )

    assert note.type == "note"
    assert note.properties["context_id"] == paper.id
    assert note.embedding is not None

    notes = list_notes(store)
    assert len(notes) == 1
    assert notes[0].id == note.id

    neighbors = store.neighbors(note.id)
    assert {n.id for n in neighbors} == {paper.id}


def test_actions_logged_as_edges(session):
    store = GraphStore(session)
    paper = store.upsert_node(type="paper", title="Another Paper")
    session.commit()

    log_action(store, "search", target_id=paper.id, details="query: transformers")
    actions = list_actions(store)
    assert len(actions) == 1
    assert actions[0].title == "search"
    assert actions[0].properties["target_id"] == paper.id

    neighbors = store.neighbors(actions[0].id)
    assert {n.id for n in neighbors} == {paper.id}


def test_gap_detection_creates_hypotheses(session, mocker):
    store = GraphStore(session)
    isolated = store.upsert_node(type="claim", title="Model scaling is smooth", embedding=None)
    session.commit()

    fake_provider = mocker.MagicMock()
    fake_provider.chat.return_value = '{"hypotheses": [{"text": "Check data quality effects", "target": "Model scaling is smooth"}]}'

    created = detect_gaps(store, provider=fake_provider)
    assert created == ["Check data quality effects"]

    hypotheses = store.list_nodes(type="hypothesis")
    assert len(hypotheses) == 1
    edges = store.list_edges()
    gap_edges = [e for e in edges if e.type == "gap_in"]
    assert len(gap_edges) == 1
    assert gap_edges[0].target_id == isolated.id


def test_gap_detection_returns_empty_without_isolated_nodes(session, mocker):
    store = GraphStore(session)
    a = store.upsert_node(type="concept", title="A")
    b = store.upsert_node(type="concept", title="B")
    store.upsert_edge(source_id=a.id, target_id=b.id, type="mentions")
    session.commit()

    fake_provider = mocker.MagicMock()
    assert detect_gaps(store, provider=fake_provider) == []
    fake_provider.chat.assert_not_called()
