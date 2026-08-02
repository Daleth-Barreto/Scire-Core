import httpx

from backend.graph.store import GraphStore
from backend.search.arxiv import ArxivAdapter, parse_atom
from backend.search.duckduckgo import DuckDuckGoAdapter, parse_html
from backend.search.openalex import OpenAlexAdapter
from backend.search.persist import persist_candidates
from backend.search.semantic_scholar import SemanticScholarAdapter
from tests.conftest import make_embed

ATOM_XML = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>http://arxiv.org/abs/1706.03762</id>
    <published>2017-06-12</published>
    <title>Attention Is All You Need</title>
    <summary>The Transformer architecture.</summary>
    <author><name>Ashish Vaswani</name></author>
    <author><name>Noam Shazeer</name></author>
  </entry>
  <entry>
    <id>http://arxiv.org/abs/2005.14165</id>
    <published>2020-05-28</published>
    <title>GPT-3</title>
    <summary>Language models are few-shot learners.</summary>
    <author><name>Tom Brown</name></author>
  </entry>
</feed>"""

SS_JSON = {
    "data": [
        {
            "title": "Graph Neural Networks",
            "authors": [{"name": "Jane Doe"}],
            "abstract": "Message passing on graphs.",
            "url": "https://www.semanticscholar.org/paper/1",
            "externalIds": {"ArXiv": "2101.00001"},
            "publicationDate": "2021-01-01",
        }
    ]
}


DDG_HTML = """
<html><body><div id="links">
<div class="result">
  <a rel="nofollow" class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.org%2Ftransformers&rut=abc">Transformers Explained</a>
  <a class="result__snippet" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.org%2Ftransformers">Attention is all you need.</a>
</div>
<div class="result">
  <a rel="nofollow" class="result__a" href="https://direct.example.net/page">No Redirect Title</a>
  <a class="result__snippet" href="https://direct.example.net/page">A direct link.</a>
</div>
</div></body></html>
"""

OPENALEX_SEARCH = {
    "meta": {"count": 1},
    "results": [
        {
            "id": "https://openalex.org/W2741809807",
            "doi": "https://doi.org/10.48550/arXiv.1706.03762",
            "title": "Attention Is All You Need",
            "publication_date": "2017-06-12",
            "authorships": [
                {"author": {"display_name": "Ashish Vaswani"}},
                {"author": {"display_name": "Noam Shazeer"}},
            ],
            "primary_location": {"landing_page_url": "https://arxiv.org/abs/1706.03762"},
            "abstract_inverted_index": {"Attention": [0], "Is": [1], "All": [2], "You": [3], "Need": [4]},
        }
    ],
}

OPENALEX_WORK = {
    "id": "https://openalex.org/W2741809807",
    "doi": "https://doi.org/10.48550/arXiv.1706.03762",
    "title": "Attention Is All You Need",
    "publication_date": "2017-06-12",
    "authorships": [{"author": {"display_name": "Ashish Vaswani"}}],
    "primary_location": {"landing_page_url": "https://arxiv.org/abs/1706.03762"},
    "abstract_inverted_index": {"Attention": [0], "Is": [1], "All": [2], "You": [3], "Need": [4]},
}


def _mock_get(mocker, response):
    return mocker.patch.object(httpx.Client, "get", return_value=response)


def test_parse_atom():
    candidates = parse_atom(ATOM_XML)
    assert len(candidates) == 2
    first = candidates[0]
    assert first.title == "Attention Is All You Need"
    assert first.authors == ["Ashish Vaswani", "Noam Shazeer"]
    assert first.external_id == "1706.03762"
    assert first.source == "arxiv"
    assert first.published == "2017-06-12"


def test_arxiv_search_parses_response(mocker):
    response = mocker.MagicMock()
    response.text = ATOM_XML
    _mock_get(mocker, response)

    candidates = ArxivAdapter().search("transformer", limit=2)
    assert len(candidates) == 2
    assert candidates[0].title == "Attention Is All You Need"


def test_arxiv_fetch_empty_returns_none(mocker):
    response = mocker.MagicMock()
    response.text = '<feed xmlns="http://www.w3.org/2005/Atom" />'
    _mock_get(mocker, response)

    assert ArxivAdapter().fetch("9999.99999") is None


def test_semantic_scholar_search_parses_response(mocker):
    response = mocker.MagicMock()
    response.json.return_value = SS_JSON
    _mock_get(mocker, response)

    candidates = SemanticScholarAdapter().search("gnn", limit=1)
    assert len(candidates) == 1
    cand = candidates[0]
    assert cand.title == "Graph Neural Networks"
    assert cand.authors == ["Jane Doe"]
    assert cand.external_id == "2101.00001"
    assert cand.source == "semanticscholar"


def test_semantic_scholar_fetch_404_returns_none(mocker):
    response = mocker.MagicMock()
    response.status_code = 404
    _mock_get(mocker, response)

    assert SemanticScholarAdapter().fetch("missing") is None


def test_openalex_search_parses_response(mocker):
    response = mocker.MagicMock()
    response.json.return_value = OPENALEX_SEARCH
    _mock_get(mocker, response)

    candidates = OpenAlexAdapter().search("attention", limit=1)
    assert len(candidates) == 1
    cand = candidates[0]
    assert cand.title == "Attention Is All You Need"
    assert cand.authors == ["Ashish Vaswani", "Noam Shazeer"]
    assert cand.external_id == "W2741809807"
    assert cand.source == "openalex"
    assert cand.published == "2017-06-12"
    assert cand.summary == "Attention Is All You Need"
    assert cand.url == "https://arxiv.org/abs/1706.03762"


def test_openalex_search_empty_results(mocker):
    response = mocker.MagicMock()
    response.json.return_value = {"meta": {"count": 0}, "results": []}
    _mock_get(mocker, response)

    assert OpenAlexAdapter().search("nothing", limit=5) == []


def test_openalex_fetch_by_openalex_id(mocker):
    response = mocker.MagicMock()
    response.json.return_value = OPENALEX_WORK
    mocked_get = _mock_get(mocker, response)

    cand = OpenAlexAdapter().fetch("W2741809807")
    assert cand is not None
    assert cand.title == "Attention Is All You Need"
    url = mocked_get.call_args[0][0]
    assert url.endswith("/W2741809807")


def test_openalex_fetch_404_returns_none(mocker):
    response = mocker.MagicMock()
    response.status_code = 404
    _mock_get(mocker, response)

    assert OpenAlexAdapter().fetch("W9999999999") is None


def test_parse_duckduckgo_html():
    candidates = parse_html(DDG_HTML)
    assert len(candidates) == 2
    first = candidates[0]
    assert first.title == "Transformers Explained"
    assert first.url == "https://example.org/transformers"
    assert first.source == "web"
    assert first.external_id == "https://example.org/transformers"
    assert first.summary == "Attention is all you need."
    assert candidates[1].title == "No Redirect Title"
    assert candidates[1].url == "https://direct.example.net/page"


def test_duckduckgo_search_parses_response(mocker):
    response = mocker.MagicMock()
    response.text = DDG_HTML
    _mock_get(mocker, response)

    candidates = DuckDuckGoAdapter().search("transformers", limit=2)
    assert len(candidates) == 2
    assert candidates[0].title == "Transformers Explained"


def test_duckduckgo_fetch_unsupported():
    assert DuckDuckGoAdapter().fetch("https://example.org") is None


def test_persist_candidates_creates_paper_and_authors(session, mocker):
    store = GraphStore(session)
    fake_embedder = mocker.MagicMock()
    fake_embedder.embed.return_value = [make_embed(0)]

    from backend.search.base import CandidateNode

    counts = persist_candidates(
        store,
        [
            CandidateNode(
                title="A Paper",
                authors=["Ann", "Bob"],
                url="https://example.org/a",
                source="arxiv",
                external_id="2301.00000",
                summary="about x",
                published="2023-01-01",
            )
        ],
        embedder=fake_embedder,
    )

    assert counts["papers"] == 1
    assert counts["authors"] == 2
    assert len(counts["paper_ids"]) == 1
    papers = store.list_nodes(type="paper")
    assert len(papers) == 1
    assert papers[0].properties["external_id"] == "2301.00000"
    assert {n.title for n in store.list_nodes(type="author")} == {"Ann", "Bob"}
    neighbors = store.neighbors(papers[0].id)
    assert {n.type for n in neighbors} == {"author"}


def test_persist_candidates_deduplicates_papers_and_authors(session, mocker):
    store = GraphStore(session)
    fake_embedder = mocker.MagicMock()
    fake_embedder.embed.return_value = [make_embed(0)]

    from backend.search.base import CandidateNode

    candidate = CandidateNode(
        title="A Paper",
        authors=["Ann", "Bob"],
        url="https://example.org/a",
        source="arxiv",
        external_id="2301.00000",
        summary="about x",
        published="2023-01-01",
    )
    first = persist_candidates(store, [candidate], embedder=fake_embedder)
    second = persist_candidates(store, [candidate], embedder=fake_embedder)

    assert first["papers"] == 1
    assert second["papers"] == 0
    assert second["authors"] == 0
    assert first["paper_ids"] == second["paper_ids"]
    assert len(store.list_nodes(type="paper")) == 1
    assert len(store.list_nodes(type="author")) == 2
    assert len(store.list_edges()) == 2

    shared = CandidateNode(
        title="Another Paper",
        authors=["Ann", "Carl"],
        url="https://example.org/b",
        source="arxiv",
        external_id="2301.00001",
    )
    persist_candidates(store, [shared], embedder=fake_embedder)
    assert len(store.list_nodes(type="author")) == 3
    assert len(store.list_edges()) == 4
