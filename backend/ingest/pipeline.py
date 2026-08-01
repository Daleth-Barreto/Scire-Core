import json
import re
from pathlib import Path
from typing import TypedDict

import httpx

from backend.core.providers import ChatMessage, LLMProvider, get_embedder, get_provider
from backend.graph.store import GraphStore
from backend.ingest.chunker import chunk_text
from backend.ingest.parser import extract_text

EXTRACTION_PROMPT = """Extract research entities from the text below. Respond with JSON only, in this exact shape:
{{"authors": ["..."], "concepts": ["..."], "claims": ["..."]}}

Text:
{chunk}"""


class IngestCounts(TypedDict):
    authors: int
    concepts: int
    claims: int
    chunks: int
    paper_id: str


def _parse_entities(raw: str) -> dict[str, list[str]]:
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip())
    data = json.loads(text)
    return {
        "authors": list(data.get("authors", [])),
        "concepts": list(data.get("concepts", [])),
        "claims": list(data.get("claims", [])),
    }


class IngestPipeline:
    def __init__(
        self,
        store: GraphStore,
        *,
        provider: LLMProvider | None = None,
        embedder: LLMProvider | None = None,
    ) -> None:
        self._store = store
        self._provider = provider or get_provider()
        self._embedder = embedder or get_embedder()
        self._created = False

    def ingest(self, path: str | Path, *, title: str | None = None) -> IngestCounts:
        text = extract_text(path)
        chunks = chunk_text(text)
        embeddings = self._embedder.embed(chunks)

        paper = self._store.upsert_node(
            type="paper",
            title=title or Path(path).stem,
            summary=text[:2000],
            embedding=embeddings[0] if embeddings else None,
        )

        counts: IngestCounts = {
            "authors": 0,
            "concepts": 0,
            "claims": 0,
            "chunks": 0,
            "paper_id": paper.id,
        }
        for idx, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            response = self._provider.chat(
                [ChatMessage(role="user", content=EXTRACTION_PROMPT.format(chunk=chunk))]
            )
            entities = _parse_entities(response)

            for author in entities["authors"]:
                node = self._upsert_entity("author", author, paper_id=paper.id, chunk_idx=idx)
                self._store.upsert_edge(
                    source_id=node.id,
                    target_id=paper.id,
                    type="authored_by",
                    properties={"chunk": idx},
                )
                counts["authors"] += int(self._created)

            for concept in entities["concepts"]:
                node = self._upsert_entity("concept", concept, chunk_idx=idx)
                self._store.upsert_edge(
                    source_id=paper.id,
                    target_id=node.id,
                    type="mentions",
                    properties={"chunk": idx},
                )
                counts["concepts"] += int(self._created)

            for claim in entities["claims"]:
                node = self._upsert_entity("claim", claim, chunk_idx=idx)
                self._store.upsert_edge(
                    source_id=paper.id,
                    target_id=node.id,
                    type="mentions",
                    properties={"chunk": idx},
                )
                counts["claims"] += int(self._created)

        counts["chunks"] = len(chunks)
        counts["paper_id"] = paper.id
        return counts

    def _upsert_entity(
        self,
        type: str,
        title: str,
        *,
        paper_id: str | None = None,
        chunk_idx: int = 0,
    ):
        existing = self._store.find_by_title(title, type=type)
        if existing:
            self._created = False
            return existing[0]
        self._created = True
        properties = {"source_paper": paper_id} if paper_id else None
        return self._store.upsert_node(
            type=type,
            title=title,
            embedding=self._embed_safe(title),
            properties=properties,
        )

    def _embed_safe(self, text: str) -> list[float] | None:
        try:
            return self._embedder.embed([text])[0]
        except (httpx.HTTPError, NotImplementedError, ValueError):
            return None
