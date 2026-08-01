from backend.graph.models import Node
from backend.graph.store import GraphStore


def log_action(
    store: GraphStore,
    action: str,
    *,
    target_id: str | None = None,
    details: str | None = None,
) -> Node:
    node = store.upsert_node(
        type="action",
        title=action,
        summary=details,
        properties={"target_id": target_id},
    )
    if target_id:
        store.upsert_edge(source_id=node.id, target_id=target_id, type="mentions")
    return node


def list_actions(store: GraphStore) -> list[Node]:
    return store.list_nodes(type="action")
