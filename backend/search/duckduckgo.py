from html.parser import HTMLParser
from urllib.parse import unquote

import httpx

from backend.search.base import CandidateNode, SearchAdapter


def _decode_redirect(href: str) -> str:
    if "uddg=" in href:
        encoded = href.split("uddg=", 1)[1].split("&", 1)[0]
        return unquote(encoded)
    return href


class _ResultParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.results: list[CandidateNode] = []
        self._current: CandidateNode | None = None
        self._href: str | None = None
        self._in_title = False
        self._in_snippet = False
        self._title_parts: list[str] = []
        self._snippet_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = dict(attrs or [])
        classes = (attr_map.get("class") or "").split()
        if tag == "a" and "result__a" in classes:
            self._in_title = True
            self._href = attr_map.get("href")
            self._title_parts = []
        elif tag == "a" and "result__snippet" in classes:
            self._in_snippet = True
            self._snippet_parts = []

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self._title_parts.append(data)
        elif self._in_snippet:
            self._snippet_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._in_title:
            self._in_title = False
            title = " ".join("".join(self._title_parts).split())
            if title and self._href:
                url = _decode_redirect(self._href)
                self._current = CandidateNode(
                    title=title,
                    url=url,
                    source="web",
                    external_id=url,
                )
                self.results.append(self._current)
            self._href = None
        elif tag == "a" and self._in_snippet:
            self._in_snippet = False
            if self._current is not None:
                self._current.summary = " ".join("".join(self._snippet_parts).split())


def parse_html(html_text: str) -> list[CandidateNode]:
    parser = _ResultParser()
    parser.feed(html_text)
    return parser.results


class DuckDuckGoAdapter(SearchAdapter):
    SEARCH_URL = "https://duckduckgo.com/html/"

    def __init__(self, client: httpx.Client | None = None) -> None:
        self._client = client or httpx.Client(
            timeout=30.0, follow_redirects=True, headers={"User-Agent": "scire/0.1"}
        )

    def search(self, query: str, limit: int = 10) -> list[CandidateNode]:
        response = self._client.get(self.SEARCH_URL, params={"q": query})
        response.raise_for_status()
        return parse_html(response.text)[:limit]

    def fetch(self, external_id: str) -> CandidateNode | None:
        return None
