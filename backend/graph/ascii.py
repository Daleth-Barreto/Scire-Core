from backend.graph.store import GraphStore


def render_tree(
    store: GraphStore,
    root_id: str,
    *,
    max_depth: int = 3,
    max_children: int = 8,
) -> str:
    lines: list[str] = []
    visited: set[str] = set()

    def walk(node_id: str, depth: int) -> None:
        node = store.get_node(node_id)
        if node is None or node_id in visited:
            return
        visited.add(node_id)
        lines.append(f"{'  ' * depth}- [{node.type}] {node.title}")
        if depth >= max_depth:
            return
        neighbors = sorted(store.neighbors(node_id), key=lambda n: (n.type, n.title))
        for neighbor in neighbors[:max_children]:
            walk(neighbor.id, depth + 1)

    walk(root_id, 0)
    return "\n".join(lines)


def find_hub(store: GraphStore) -> str | None:
    nodes = store.list_nodes()
    if not nodes:
        return None
    degree = {n.id: 0 for n in nodes}
    for edge in store.list_edges():
        if edge.source_id in degree:
            degree[edge.source_id] += 1
        if edge.target_id in degree:
            degree[edge.target_id] += 1
    if not degree:
        return None
    return max(degree.items(), key=lambda item: item[1])[0]
