from typing import TypedDict

import httpx

from backend.core.providers import LLMProvider, get_embedder
from backend.graph.models import Node
from backend.graph.store import GraphStore
from backend.search.base import CandidateNode


class PersistCounts(TypedDict):
    papers: int
    authors: int
    paper_ids: list[str]


def _existing_paper(store: GraphStore, candidate: CandidateNode) -> Node | None:
    if not candidate.external_id:
        return None
    matches = store.find_by_property("external_id", candidate.external_id, type="paper")
    for node in matches:
        if node.properties.get("source") == candidate.source:
            return node
    return None


def persist_candidates(
    store: GraphStore,
    candidates: list[CandidateNode],
    embedder: LLMProvider | None = None,
) -> PersistCounts:
    embedder = embedder or get_embedder()
    counts: PersistCounts = {"papers": 0, "authors": 0, "paper_ids": []}
    for candidate in candidates:
        existing = _existing_paper(store, candidate)
        if existing is not None:
            counts["paper_ids"].append(existing.id)
            node = existing
        else:
            embedding = None
            try:
                embedding = embedder.embed([f"{candidate.title}\n{candidate.summary}"])[0]
            except (NotImplementedError, ValueError, httpx.HTTPError):
                pass
            node = store.upsert_node(
                type="paper",
                title=candidate.title,
                summary=candidate.summary[:2000],
                embedding=embedding,
                properties={
                    "source": candidate.source,
                    "external_id": candidate.external_id,
                    "url": candidate.url,
                    "authors": candidate.authors,
                    "published": candidate.published,
                },
            )
            counts["papers"] += 1
            counts["paper_ids"].append(node.id)
        for author in candidate.authors[:10]:
            matches = store.find_by_title(author, type="author")
            if matches:
                author_node = matches[0]
            else:
                author_node = store.upsert_node(
                    type="author",
                    title=author,
                    properties={"source_paper": node.id},
                )
                counts["authors"] += 1
            store.upsert_edge(
                source_id=author_node.id,
                target_id=node.id,
                type="authored_by",
            )
    return counts
