import xml.etree.ElementTree as ET
from typing import Any

import httpx

from backend.core.cache import ttl_cache
from backend.search.base import CandidateNode, SearchAdapter

BASE_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest"
ARTICLE_URL = "https://europepmc.org/article"


def _from_article(article: dict[str, Any]) -> CandidateNode:
    source = article.get("source", "")
    ext_id = article.get("id", "")
    return CandidateNode(
        title=article.get("title", ""),
        authors=[a.strip() for a in article.get("authorString", "").split(",") if a.strip()],
        url=f"{ARTICLE_URL}/{source}/{ext_id}",
        source="europepmc",
        external_id=f"{source}:{ext_id}",
        summary=article.get("abstractText") or "",
        published=article.get("firstPublicationDate") or article.get("pubYear"),
    )


def _fulltext_from_xml(xml_text: str) -> str:
    root = ET.fromstring(xml_text)
    body = root.find(".//body")
    if body is None:
        return ""
    paragraphs = [
        " ".join(p.itertext()).strip()
        for p in body.iter()
        if p.tag.rsplit("}", 1)[-1] == "p"
    ]
    text = "\n\n".join(p for p in paragraphs if p)
    if text:
        return text
    return " ".join(body.itertext()).strip()


class EuropePMCAdapter(SearchAdapter):
    def __init__(self, client: httpx.Client | None = None) -> None:
        self._client = client or httpx.Client(timeout=30.0)

    @ttl_cache(ttl=300.0)
    def search(self, query: str, limit: int = 10) -> list[CandidateNode]:
        response = self._client.get(
            f"{BASE_URL}/search",
            params={"query": query, "format": "json", "pageSize": limit},
        )
        response.raise_for_status()
        return [
            _from_article(a)
            for a in response.json().get("resultList", {}).get("result", [])
        ]

    def fetch(self, external_id: str) -> CandidateNode | None:
        _, sep, value = external_id.partition(":")
        query = value if sep else external_id
        response = self._client.get(
            f"{BASE_URL}/search",
            params={"query": f"EXT_ID:{query}", "format": "json"},
        )
        if response.status_code == 404:
            return None
        response.raise_for_status()
        results = response.json().get("resultList", {}).get("result", [])
        return _from_article(results[0]) if results else None

    def fetch_fulltext(self, external_id: str) -> str | None:
        source, sep, value = external_id.partition(":")
        if sep and source.upper() == "PMC":
            return self._fulltext_xml(value)
        query = value if sep else external_id
        response = self._client.get(
            f"{BASE_URL}/search",
            params={"query": f"EXT_ID:{query}", "format": "json"},
        )
        if response.status_code != 200:
            return None
        results = response.json().get("resultList", {}).get("result", [])
        pmcid = results[0].get("pmcid") if results else None
        if not pmcid:
            return None
        return self._fulltext_xml(pmcid)

    def _fulltext_xml(self, pmcid: str) -> str | None:
        response = self._client.get(f"{BASE_URL}/PMC/{pmcid}/fullTextXML")
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return _fulltext_from_xml(response.text)
