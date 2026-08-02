from dataclasses import dataclass

from backend.graph.models import Node
from backend.graph.store import GraphStore

SOURCE_WEIGHTS = {
    "arxiv": 1.0,
    "openalex": 1.0,
    "europepmc": 1.0,
    "semanticscholar": 0.8,
    "web": 0.5,
    "duckduckgo": 0.5,
}

METHOD_EVIDENCE_TYPES = ("repo", "claim", "hypothesis")


@dataclass
class RankedPaper:
    node: Node
    score: float
    relevance: float
    citations: float
    method: float
    provenance: float


def _citation_counts(store: GraphStore) -> dict[str, int]:
    counts: dict[str, int] = {}
    for edge in store.list_edges():
        if edge.type == "cites":
            counts[edge.target_id] = counts.get(edge.target_id, 0) + 1
    return counts


def _method_score(store: GraphStore, node_id: str) -> float:
    kinds = {n.type for n in store.neighbors(node_id)}
    score = 0.0
    if "repo" in kinds:
        score += 0.5
    if "claim" in kinds:
        score += 0.3
    if "hypothesis" in kinds:
        score += 0.2
    return min(score, 1.0)


def rank_papers(
    store: GraphStore,
    query_embedding: list[float],
    top_k: int = 10,
) -> list[RankedPaper]:
    hits = store.search(query_embedding, top_k=top_k, node_type="paper")
    if not hits:
        return []

    citations = _citation_counts(store)
    max_external = max(
        (int(node.properties.get("cited_by_count", 0)) for node, _ in hits),
        default=0,
    )
    max_total = max(max_external, max(citations.values(), default=0), 1)

    ranked: list[RankedPaper] = []
    for node, distance in hits:
        relevance = max(0.0, 1.0 - distance)
        in_graph = citations.get(node.id, 0)
        external = int(node.properties.get("cited_by_count", 0))
        citations_score = min(1.0, (in_graph + external) / max_total)
        method = _method_score(store, node.id)
        provenance = SOURCE_WEIGHTS.get(node.properties.get("source", ""), 0.5)

        score = 0.35 * relevance + 0.25 * citations_score + 0.2 * method + 0.2 * provenance
        ranked.append(
            RankedPaper(
                node=node,
                score=round(score, 4),
                relevance=round(relevance, 4),
                citations=round(citations_score, 4),
                method=round(method, 4),
                provenance=round(provenance, 4),
            )
        )
    return sorted(ranked, key=lambda r: r.score, reverse=True)
