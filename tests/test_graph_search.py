from backend.graph.store import GraphStore
from tests.conftest import make_embed


def test_search_returns_nearest_neighbors(session):
    store = GraphStore(session)
    store.upsert_node(type="paper", title="Transformers", embedding=make_embed(0))
    store.upsert_node(type="paper", title="Graphs", embedding=make_embed(1))
    store.upsert_node(type="concept", title="Attention", embedding=make_embed(2))
    session.commit()

    results = store.search(make_embed(0), top_k=2)
    assert len(results) == 2
    assert results[0][0].title == "Transformers"
    assert results[0][1] <= results[1][1]


def test_search_empty_graph_returns_empty(session):
    store = GraphStore(session)
    assert store.search(make_embed(0), top_k=5) == []


def test_search_orders_by_cosine_distance(session):
    store = GraphStore(session)
    store.upsert_node(type="paper", title="N1", embedding=make_embed(0))
    store.upsert_node(type="paper", title="N2", embedding=[0.0] * 3072)
    session.commit()

    results = store.search(make_embed(0), top_k=2)
    assert results[0][0].title == "N1"
    assert len(results) == 2
