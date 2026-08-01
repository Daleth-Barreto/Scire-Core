from backend.graph.store import GraphStore


def test_node_upsert_creates_and_updates(session):
    store = GraphStore(session)
    node = store.upsert_node(
        type="paper", title="A Paper", summary="about x", embedding=[0.1] * 3072
    )
    session.commit()
    node_id = node.id
    assert node.title == "A Paper"

    same = store.upsert_node(
        node_id=node_id,
        type="paper",
        title="A Paper v2",
        embedding=[0.2] * 3072,
    )
    session.commit()
    assert same.id == node_id
    assert same.title == "A Paper v2"
    assert store.get_node(node_id).title == "A Paper v2"


def test_edge_upsert_and_deduplication(session):
    store = GraphStore(session)
    a = store.upsert_node(type="paper", title="A")
    b = store.upsert_node(type="paper", title="B")
    session.commit()

    e1 = store.upsert_edge(source_id=a.id, target_id=b.id, type="cites")
    e2 = store.upsert_edge(source_id=a.id, target_id=b.id, type="cites")
    session.commit()
    assert e1.id == e2.id


def test_neighbors_one_hop(session):
    store = GraphStore(session)
    a = store.upsert_node(type="author", title="A")
    b = store.upsert_node(type="paper", title="B")
    c = store.upsert_node(type="concept", title="C")
    store.upsert_edge(source_id=a.id, target_id=b.id, type="authored_by")
    store.upsert_edge(source_id=b.id, target_id=c.id, type="mentions")
    session.commit()

    neighbors = store.neighbors(a.id)
    assert {n.id for n in neighbors} == {b.id}
    assert {n.id for n in store.neighbors(b.id)} == {a.id, c.id}
    two_hop = store.neighbors(a.id, hops=2)
    assert {n.id for n in two_hop} == {b.id, c.id}


def test_empty_graph_has_no_neighbors(session):
    store = GraphStore(session)
    assert store.neighbors("missing") == []
    assert store.list_nodes() == []
