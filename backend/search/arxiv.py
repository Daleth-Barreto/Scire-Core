import xml.etree.ElementTree as ET

import httpx

from backend.core.cache import ttl_cache
from backend.search.base import CandidateNode, SearchAdapter

ATOM = "{http://www.w3.org/2005/Atom}"


def parse_atom(xml_text: str) -> list[CandidateNode]:
    root = ET.fromstring(xml_text)
    out: list[CandidateNode] = []
    for entry in root.findall(f"{ATOM}entry"):
        url = entry.findtext(f"{ATOM}id", default="").strip()
        external_id = url.rsplit("/abs/", 1)[-1] if "/abs/" in url else ""
        authors = [
            a.findtext(f"{ATOM}name", default="").strip() for a in entry.findall(f"{ATOM}author")
        ]
        out.append(
            CandidateNode(
                title=entry.findtext(f"{ATOM}title", default="").strip(),
                authors=authors,
                url=url,
                source="arxiv",
                external_id=external_id,
                summary=entry.findtext(f"{ATOM}summary", default="").strip(),
                published=entry.findtext(f"{ATOM}published", default="").strip() or None,
            )
        )
    return out


class ArxivAdapter(SearchAdapter):
    BASE_URL = "https://export.arxiv.org/api/query"

    def __init__(self, client: httpx.Client | None = None) -> None:
        self._client = client or httpx.Client(timeout=30.0)

    @ttl_cache(ttl=300.0)
    def search(self, query: str, limit: int = 10) -> list[CandidateNode]:
        response = self._client.get(
            self.BASE_URL,
            params={
                "search_query": f"all:{query}",
                "max_results": limit,
                "sortBy": "relevance",
            },
        )
        response.raise_for_status()
        return parse_atom(response.text)

    def fetch(self, external_id: str) -> CandidateNode | None:
        response = self._client.get(self.BASE_URL, params={"id_list": external_id})
        response.raise_for_status()
        results = parse_atom(response.text)
        return results[0] if results else None
