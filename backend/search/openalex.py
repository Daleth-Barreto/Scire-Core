from typing import Any

import httpx

from backend.search.base import CandidateNode, SearchAdapter

BASE_URL = "https://api.openalex.org/works"


def _reconstruct_abstract(inverted: dict[str, list[int]] | None) -> str:
    if not inverted:
        return ""
    positioned: list[tuple[int, str]] = []
    for word, positions in inverted.items():
        positioned.extend((pos, word) for pos in positions)
    positioned.sort()
    return " ".join(word for _, word in positioned)


def _from_work(work: dict[str, Any]) -> CandidateNode:
    openalex_id = work.get("id", "")
    external_id = openalex_id.rsplit("/", 1)[-1]
    primary = work.get("primary_location") or {}
    landing = primary.get("landing_page_url") or ""
    doi = work.get("doi") or ""
    return CandidateNode(
        title=work.get("title", ""),
        authors=[
            a.get("author", {}).get("display_name", "") for a in work.get("authorships", [])
        ],
        url=landing or doi,
        source="openalex",
        external_id=external_id,
        summary=_reconstruct_abstract(work.get("abstract_inverted_index")),
        published=work.get("publication_date"),
        cited_by_count=int(work.get("cited_by_count") or 0),
    )


class OpenAlexAdapter(SearchAdapter):
    def __init__(self, client: httpx.Client | None = None) -> None:
        self._client = client or httpx.Client(timeout=30.0)

    def search(self, query: str, limit: int = 10) -> list[CandidateNode]:
        response = self._client.get(
            BASE_URL,
            params={"search": query, "per-page": limit},
        )
        response.raise_for_status()
        return [_from_work(work) for work in response.json().get("results", [])]

    def fetch(self, external_id: str) -> CandidateNode | None:
        response = self._client.get(f"{BASE_URL}/{external_id}")
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return _from_work(response.json())
