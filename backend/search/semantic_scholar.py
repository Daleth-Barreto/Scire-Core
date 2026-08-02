from typing import Any

import httpx

from backend.core.cache import ttl_cache
from backend.search.base import CandidateNode, SearchAdapter

FIELDS = "title,authors,abstract,url,externalIds,publicationDate"


def _from_paper(paper: dict[str, Any]) -> CandidateNode:
    external = paper.get("externalIds") or {}
    external_id = (
        external.get("ArXiv")
        or external.get("DOI")
        or external.get("CorpusId")
        or paper.get("paperId")
        or ""
    )
    return CandidateNode(
        title=paper.get("title", ""),
        authors=[a.get("name", "") for a in paper.get("authors", [])],
        url=paper.get("url", ""),
        source="semanticscholar",
        external_id=str(external_id),
        summary=paper.get("abstract") or "",
        published=paper.get("publicationDate"),
    )


class SemanticScholarAdapter(SearchAdapter):
    BASE_URL = "https://api.semanticscholar.org/graph/v1"

    def __init__(self, client: httpx.Client | None = None) -> None:
        self._client = client or httpx.Client(timeout=30.0)

    @ttl_cache(ttl=300.0)
    def search(self, query: str, limit: int = 10) -> list[CandidateNode]:
        response = self._client.get(
            f"{self.BASE_URL}/paper/search",
            params={"query": query, "limit": limit, "fields": FIELDS},
        )
        response.raise_for_status()
        return [_from_paper(p) for p in response.json().get("data", [])]

    def fetch(self, external_id: str) -> CandidateNode | None:
        response = self._client.get(
            f"{self.BASE_URL}/paper/{external_id}", params={"fields": FIELDS}
        )
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return _from_paper(response.json())
