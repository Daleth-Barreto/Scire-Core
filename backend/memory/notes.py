from backend.core.providers import LLMProvider, get_embedder
from backend.graph.models import Node
from backend.graph.store import GraphStore


def add_note(
    store: GraphStore,
    text: str,
    *,
    context_id: str | None = None,
    embedder: LLMProvider | None = None,
) -> Node:
    embedder = embedder or get_embedder()
    embedding = None
    try:
        embedding = embedder.embed([text])[0]
    except (NotImplementedError, ValueError):
        pass
    node = store.upsert_node(
        type="note",
        title=text[:80],
        summary=text,
        embedding=embedding,
        properties={"context_id": context_id},
    )
    if context_id:
        store.upsert_edge(source_id=node.id, target_id=context_id, type="mentions")
    return node


def list_notes(store: GraphStore) -> list[Node]:
    return store.list_nodes(type="note")
