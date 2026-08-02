import json
import re
from dataclasses import dataclass, field

import httpx

from backend.core.providers import ChatMessage, LLMProvider, get_provider
from backend.search.arxiv import ArxivAdapter
from backend.search.base import CandidateNode, SearchAdapter
from backend.search.europepmc import EuropePMCAdapter
from backend.search.openalex import OpenAlexAdapter

RESEARCHER_PROMPT = """You are the researcher in a deep-research pipeline.
Synthesize the sources below into a structured analysis. Do not invent facts
outside the sources. Respond with JSON only:
{{"sections": [{{"heading": "...", "points": ["..."]}}], "conflicts": ["..."], "gaps": ["..."]}}

Topic: {topic}

Sources:
{sources}"""

WRITER_PROMPT = """You are the writer in a deep-research pipeline. Write a
research brief in Markdown using the researcher's analysis and the numbered
sources. Cite sources inline with [n] matching the numbered list below. Every
factual claim must carry a citation. End with a "Sources" section listing the
numbered sources.

Topic: {topic}

Researcher analysis:
{analysis}

Sources:
{sources}"""

VERIFIER_PROMPT = """You are the verifier in a deep-research pipeline. Check
the brief against the numbered sources. Flag any claim that lacks a citation
or is not supported by the sources, and any [n] citation that is out of range.
Respond with JSON only:
{{"verified": true|false, "issues": ["..."]}}

Brief:
{brief}

Sources:
{sources}"""


@dataclass
class SourceNote:
    title: str
    url: str
    source: str
    summary: str = ""
    authors: list[str] = field(default_factory=list)

    @classmethod
    def from_candidate(cls, candidate: CandidateNode) -> "SourceNote":
        return cls(
            title=candidate.title,
            url=candidate.url,
            source=candidate.source,
            summary=candidate.summary[:800],
            authors=candidate.authors[:5],
        )


@dataclass
class ResearchBrief:
    topic: str
    markdown: str
    sources: list[SourceNote] = field(default_factory=list)
    verified: bool = False
    issues: list[str] = field(default_factory=list)


def _parse_json(raw: str) -> dict:
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip())
    return json.loads(text)


def _format_sources(sources: list[SourceNote]) -> str:
    lines = []
    for i, source in enumerate(sources, start=1):
        lines.append(f"[{i}] {source.title} — {source.url}")
        if source.authors:
            lines.append(f"    authors: {', '.join(source.authors)}")
        if source.summary:
            lines.append(f"    {source.summary}")
    return "\n".join(lines)


def gather_sources(
    topic: str,
    limit: int = 5,
    adapters: list[SearchAdapter] | None = None,
) -> list[SourceNote]:
    adapters = adapters or [ArxivAdapter(), OpenAlexAdapter(), EuropePMCAdapter()]
    notes: list[SourceNote] = []
    seen: set[tuple[str, str]] = set()
    for adapter in adapters:
        try:
            for candidate in adapter.search(topic, limit=limit):
                key = (candidate.source, candidate.external_id)
                if key in seen:
                    continue
                seen.add(key)
                notes.append(SourceNote.from_candidate(candidate))
        except httpx.HTTPError:
            continue
    return notes


def deepresearch(
    topic: str,
    *,
    sources: list[SourceNote] | None = None,
    limit: int = 5,
    provider: LLMProvider | None = None,
) -> ResearchBrief:
    provider = provider or get_provider()
    sources = sources if sources is not None else gather_sources(topic, limit=limit)
    if not sources:
        raise ValueError("no sources found for topic (check network/adapters)")

    source_block = _format_sources(sources)
    research = _parse_json(
        provider.chat(
            [ChatMessage(role="user", content=RESEARCHER_PROMPT.format(topic=topic, sources=source_block))]
        )
    )
    brief = provider.chat(
        [
            ChatMessage(
                role="user",
                content=WRITER_PROMPT.format(
                    topic=topic,
                    analysis=json.dumps(research, indent=2),
                    sources=source_block,
                ),
            )
        ]
    )
    verifier_raw = provider.chat(
        [
            ChatMessage(
                role="user",
                content=VERIFIER_PROMPT.format(brief=brief, sources=source_block),
            )
        ]
    )
    try:
        verdict = _parse_json(verifier_raw)
        verified = bool(verdict.get("verified", False))
        issues = [str(item) for item in verdict.get("issues", [])]
    except (json.JSONDecodeError, TypeError):
        verified = False
        issues = []

    return ResearchBrief(
        topic=topic,
        markdown=brief.strip(),
        sources=sources,
        verified=verified,
        issues=issues,
    )
