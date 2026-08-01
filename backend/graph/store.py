from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from backend.graph.models import Edge, Node


class GraphStore:
    def __init__(self, session: Session) -> None:
        self._session = session

    def upsert_node(
        self,
        *,
        type: str,
        title: str,
        summary: str | None = None,
        embedding: list[float] | None = None,
        properties: dict | None = None,
        node_id: str | None = None,
    ) -> Node:
        node = self._session.get(Node, node_id) if node_id else None
        if node is None:
            node = Node(
                type=type,
                title=title,
                summary=summary,
                embedding=embedding,
                properties=properties or {},
            )
            if node_id:
                node.id = node_id
            self._session.add(node)
        else:
            node.type = type
            node.title = title
            node.summary = summary
            if embedding is not None:
                node.embedding = embedding
            if properties:
                node.properties = {**node.properties, **properties}
        self._session.flush()
        return node

    def get_node(self, node_id: str) -> Node | None:
        return self._session.get(Node, node_id)

    def upsert_edge(
        self,
        *,
        source_id: str,
        target_id: str,
        type: str,
        properties: dict | None = None,
    ) -> Edge:
        edge = self._session.scalar(
            select(Edge).where(
                Edge.source_id == source_id,
                Edge.target_id == target_id,
                Edge.type == type,
            )
        )
        if edge is None:
            edge = Edge(
                source_id=source_id,
                target_id=target_id,
                type=type,
                properties=properties or {},
            )
            self._session.add(edge)
        else:
            if properties:
                edge.properties = {**edge.properties, **properties}
        self._session.flush()
        return edge

    def neighbors(self, node_id: str, hops: int = 1) -> list[Node]:
        if hops <= 1:
            edges = self._session.scalars(
                select(Edge).where(or_(Edge.source_id == node_id, Edge.target_id == node_id))
            ).all()
            neighbor_ids = {e.target_id if e.source_id == node_id else e.source_id for e in edges}
            return self._nodes_by_ids(neighbor_ids)

        current = {node_id}
        visited: set[str] = set()
        result_ids: set[str] = set()
        for _ in range(hops):
            edges = self._session.scalars(
                select(Edge).where(or_(Edge.source_id.in_(current), Edge.target_id.in_(current)))
            ).all()
            next_ids = set()
            for edge in edges:
                for nid in (edge.source_id, edge.target_id):
                    if nid not in visited:
                        next_ids.add(nid)
            visited |= current
            current = next_ids
            result_ids |= current
        result_ids.discard(node_id)
        return self._nodes_by_ids(result_ids)

    def search(
        self,
        query_embedding: list[float],
        top_k: int = 10,
        node_type: str | None = None,
    ) -> list[tuple[Node, float]]:
        if not query_embedding:
            return []
        distance = Node.embedding.cosine_distance(query_embedding)
        stmt = select(Node, distance).where(Node.embedding.isnot(None))
        if node_type:
            stmt = stmt.where(Node.type == node_type)
        rows = self._session.execute(stmt.order_by(distance).limit(top_k)).all()
        return [(node, float(dist)) for node, dist in rows]

    def list_nodes(self, type: str | None = None) -> list[Node]:
        stmt = select(Node)
        if type:
            stmt = stmt.where(Node.type == type)
        return list(self._session.scalars(stmt.order_by(Node.created_at.desc())).all())

    def find_by_title(self, title: str, type: str | None = None) -> list[Node]:
        stmt = select(Node).where(Node.title == title)
        if type:
            stmt = stmt.where(Node.type == type)
        return list(self._session.scalars(stmt))

    def find_by_property(self, key: str, value: str, type: str | None = None) -> list[Node]:
        stmt = select(Node).where(Node.properties[key].astext == value)
        if type:
            stmt = stmt.where(Node.type == type)
        return list(self._session.scalars(stmt))

    def list_edges(self) -> list[Edge]:
        return list(self._session.scalars(select(Edge)).all())

    def _nodes_by_ids(self, ids: set[str]) -> list[Node]:
        if not ids:
            return []
        return list(self._session.scalars(select(Node).where(Node.id.in_(ids))).all())
