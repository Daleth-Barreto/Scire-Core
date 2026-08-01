from typing import Any

from backend.graph.store import GraphStore


def export_graph(store: GraphStore) -> dict[str, Any]:
    return {
        "nodes": [
            {
                "id": n.id,
                "type": n.type,
                "title": n.title,
                "summary": n.summary,
                "properties": n.properties,
            }
            for n in store.list_nodes()
        ],
        "edges": [
            {
                "id": e.id,
                "source_id": e.source_id,
                "target_id": e.target_id,
                "type": e.type,
                "properties": e.properties,
            }
            for e in store.list_edges()
        ],
    }


def import_graph(store: GraphStore, data: dict[str, Any]) -> dict[str, int]:
    counts = {"nodes": 0, "edges": 0}
    for node in data.get("nodes", []):
        store.upsert_node(
            node_id=node["id"],
            type=node["type"],
            title=node["title"],
            summary=node.get("summary"),
            properties=node.get("properties") or {},
        )
        counts["nodes"] += 1
    for edge in data.get("edges", []):
        store.upsert_edge(
            source_id=edge["source_id"],
            target_id=edge["target_id"],
            type=edge["type"],
            properties=edge.get("properties") or {},
        )
        counts["edges"] += 1
    return counts
