import json
import re

import httpx

from backend.core.providers import ChatMessage, LLMProvider, get_provider
from backend.graph.store import GraphStore

GAPS_PROMPT = """You are helping a researcher find gaps in a knowledge graph.
Here are isolated nodes (not connected to anything) and current claims.
Propose up to 3 research hypotheses that connect or challenge them.
Respond with JSON only: {{"hypotheses": [{{"text": "...", "target": "<node title>"}}]}}

Isolated nodes:
{isolated}

Claims:
{claims}"""


def _parse_hypotheses(raw: str) -> list[dict]:
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip())
    data = json.loads(text)
    return list(data.get("hypotheses", []))


def detect_gaps(
    store: GraphStore,
    *,
    provider: LLMProvider | None = None,
    max_hypotheses: int = 3,
) -> list[str]:
    provider = provider or get_provider()

    edges = store.list_edges()
    connected: set[str] = set()
    for edge in edges:
        connected.add(edge.source_id)
        connected.add(edge.target_id)

    all_nodes = store.list_nodes()
    isolated = [n for n in all_nodes if n.id not in connected and n.type not in {"action", "note"}]
    claims = store.list_nodes(type="claim")

    if not isolated:
        return []

    isolated_lines = "\n".join(f"- ({n.type}) {n.title}" for n in isolated[:30])
    claims_lines = "\n".join(f"- {n.title}" for n in claims[:20])
    try:
        response = provider.chat(
            [
                ChatMessage(
                    role="user",
                    content=GAPS_PROMPT.format(isolated=isolated_lines, claims=claims_lines),
                )
            ]
        )
    except (httpx.HTTPError, ValueError):
        return []

    by_title = {n.title: n for n in isolated}
    created: list[str] = []
    for hypothesis in _parse_hypotheses(response)[:max_hypotheses]:
        text = hypothesis.get("text", "").strip()
        target = hypothesis.get("target", "")
        if not text:
            continue
        node = store.upsert_node(
            type="hypothesis",
            title=text,
            properties={"target": target},
        )
        if target in by_title:
            store.upsert_edge(source_id=node.id, target_id=by_title[target].id, type="gap_in")
        created.append(text)
    return created
