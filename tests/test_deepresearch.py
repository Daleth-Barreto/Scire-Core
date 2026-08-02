import json

import httpx
import pytest

from backend.core.providers import ChatMessage
from backend.research.deepresearch import (
    ResearchBrief,
    deepresearch,
    gather_sources,
)
from backend.search.base import CandidateNode

SOURCES = [
    CandidateNode(
        title="Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks",
        authors=["Patrick Lewis"],
        url="https://arxiv.org/abs/2005.11401",
        source="arxiv",
        external_id="2005.11401",
        summary="RAG combines parametric and non-parametric memory.",
    ),
    CandidateNode(
        title="Wikipedia",
        url="https://en.wikipedia.org/wiki/Retrieval-augmented_generation",
        source="web",
        external_id="wiki:rag",
        summary="RAG augments LLMs with external knowledge retrieval.",
    ),
]


def _provider_that_returns(*responses: str):
    class FakeProvider:
        def __init__(self) -> None:
            self.calls: list[list[ChatMessage]] = []

        def chat(self, messages, model=None):
            self.calls.append(list(messages))
            return responses[len(self.calls) - 1]

    return FakeProvider()


def test_gather_sources_collects_from_adapters(mocker):
    arxiv = mocker.MagicMock()
    arxiv.search.return_value = [SOURCES[0]]
    openalex = mocker.MagicMock()
    openalex.search.return_value = []

    notes = gather_sources("rag", adapters=[arxiv, openalex])

    assert len(notes) == 1
    assert notes[0].title == "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks"
    assert notes[0].url == "https://arxiv.org/abs/2005.11401"


def test_gather_sources_degrades_on_http_error(mocker):
    broken = mocker.MagicMock()
    broken.search.side_effect = httpx.HTTPError("429")
    ok = mocker.MagicMock()
    ok.search.return_value = [SOURCES[1]]

    notes = gather_sources("rag", adapters=[broken, ok])

    assert len(notes) == 1
    assert notes[0].source == "web"


def test_deepresearch_produces_brief_with_citations(mocker):
    research = json.dumps(
        {
            "sections": [{"heading": "Approach", "points": ["RAG couples retrieval with generation"]}],
            "conflicts": [],
            "gaps": ["Evaluation on non-English corpora"],
        }
    )
    brief_md = (
        "## RAG\n\nRAG augments LLMs with retrieval [1][2]. "
        "The approach couples parametric memory with non-parametric retrieval [1].\n"
    )
    verifier = json.dumps({"verified": True, "issues": []})
    provider = _provider_that_returns(research, brief_md, verifier)

    result = deepresearch(
        "retrieval augmented generation",
        sources=SOURCES,
        provider=provider,
    )

    assert isinstance(result, ResearchBrief)
    assert result.topic == "retrieval augmented generation"
    assert "[1]" in result.markdown and "[2]" in result.markdown
    assert result.verified is True
    assert result.issues == []
    assert len(result.sources) == 2


def test_deepresearch_researcher_prompt_contains_sources(mocker):
    provider = _provider_that_returns(
        json.dumps({"sections": [], "conflicts": [], "gaps": []}),
        "brief without citations",
        json.dumps({"verified": False, "issues": ["no citations"]}),
    )

    deepresearch("rag", sources=SOURCES, provider=provider)

    researcher_prompt = provider.calls[0][0].content
    assert "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks" in researcher_prompt
    assert "https://arxiv.org/abs/2005.11401" in researcher_prompt


def test_deepresearch_verifier_reports_issues(mocker):
    provider = _provider_that_returns(
        json.dumps({"sections": [{"heading": "X", "points": ["P"]}], "conflicts": [], "gaps": []}),
        "Brief with an unsupported claim.",
        json.dumps({"verified": False, "issues": ["claim not supported by sources"]}),
    )

    result = deepresearch("rag", sources=SOURCES, provider=provider)

    assert result.verified is False
    assert "claim not supported by sources" in result.issues


def test_deepresearch_unparseable_verifier_degrades(mocker):
    provider = _provider_that_returns(
        json.dumps({"sections": [], "conflicts": [], "gaps": []}),
        "brief",
        "not json at all",
    )

    result = deepresearch("rag", sources=SOURCES, provider=provider)

    assert result.verified is False
    assert result.markdown == "brief"


def test_deepresearch_unparseable_researcher_degrades(mocker):
    provider = _provider_that_returns(
        "not json at all",
        "brief with [1]",
        json.dumps({"verified": True, "issues": []}),
    )

    result = deepresearch("rag", sources=SOURCES, provider=provider)

    assert result.markdown == "brief with [1]"
    assert result.verified is True


def test_deepresearch_without_sources_raises(mocker):
    provider = _provider_that_returns("{}", "brief", "{}")
    with pytest.raises(ValueError, match="no sources"):
        deepresearch("rag", sources=[], provider=provider)
