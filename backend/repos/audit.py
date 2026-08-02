import json
import re
from dataclasses import dataclass, field

from backend.core.providers import ChatMessage, LLMProvider, get_embedder, get_provider
from backend.graph.models import Node
from backend.graph.store import GraphStore

AUDIT_PROMPT = """Judge whether the research claim is supported by the code excerpts below.
Verdicts: "supported" (code implements it), "refuted" (code contradicts it),
"not-evidenced" (no code evidence found). Cite the exact file and line using
path:line format when supported or refuted. Respond with JSON only:
{{"verdict": "...", "evidence": "path:line", "reason": "..."}}

Claim: {claim}

Excerpts:
{context}"""


def _chunk_ref(chunk: Node) -> str:
    path = chunk.properties.get("path") or chunk.title
    start = chunk.properties.get("start_line", 1)
    return f"{path}:{start}"


def _parse_verdict(raw: str) -> dict:
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip())
    return json.loads(text)


@dataclass
class AuditVerdict:
    claim: str
    verdict: str
    evidence: str = ""
    reason: str = ""


@dataclass
class AuditReport:
    paper_title: str
    repo: str
    verdicts: list[AuditVerdict] = field(default_factory=list)

    def summary(self) -> dict[str, int]:
        counts = {"supported": 0, "refuted": 0, "not-evidenced": 0}
        for v in self.verdicts:
            counts[v.verdict] = counts.get(v.verdict, 0) + 1
        return counts


def _paper_claims(store: GraphStore, paper: Node) -> list[str]:
    claim_ids = {
        edge.target_id
        for edge in store.list_edges()
        if edge.source_id == paper.id and edge.type == "mentions"
    }
    claims = []
    for node_id in claim_ids:
        node = store.get_node(node_id)
        if node is not None and node.type == "claim":
            claims.append(node.title)
    return claims


def audit_paper(
    store: GraphStore,
    paper_title: str,
    owner: str,
    repo: str,
    *,
    top_k: int = 5,
    provider: LLMProvider | None = None,
    embedder: LLMProvider | None = None,
) -> AuditReport:
    provider = provider or get_provider()
    embedder = embedder or get_embedder()

    papers = store.find_by_title(paper_title, type="paper")
    if not papers:
        raise ValueError(f"paper not found: {paper_title}")
    paper = papers[0]

    claims = _paper_claims(store, paper)
    if not claims:
        raise ValueError(
            f"no claims extracted for paper: {paper_title} "
            "(ingest the full text first, e.g. `scire paper fulltext`)"
        )

    repo_nodes = [n for n in store.list_nodes(type="repo") if n.title == f"{owner}/{repo}"]
    if not repo_nodes:
        raise ValueError(f"repo not indexed: {owner}/{repo} (run `scire repo add {owner}/{repo}` first)")
    repo_id = repo_nodes[0].id

    report = AuditReport(paper_title=paper.title, repo=f"{owner}/{repo}")
    for claim in claims:
        embedding = embedder.embed([claim])[0]
        results = store.search(embedding, top_k=top_k, node_type="chunk")
        chunks = [node for node, _ in results if node.properties.get("repo") == repo_id]
        if not chunks:
            report.verdicts.append(AuditVerdict(claim=claim, verdict="not-evidenced"))
            continue
        context = "\n\n".join(f"--- {_chunk_ref(node)} ---\n{node.summary}" for node in chunks)
        raw = provider.chat(
            [ChatMessage(role="user", content=AUDIT_PROMPT.format(claim=claim, context=context))]
        )
        try:
            data = _parse_verdict(raw)
            report.verdicts.append(
                AuditVerdict(
                    claim=claim,
                    verdict=data.get("verdict", "not-evidenced"),
                    evidence=data.get("evidence", ""),
                    reason=data.get("reason", ""),
                )
            )
        except (json.JSONDecodeError, TypeError):
            report.verdicts.append(AuditVerdict(claim=claim, verdict="not-evidenced"))
    return report
