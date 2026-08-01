from backend.core.providers import ChatMessage, LLMProvider, get_embedder, get_provider
from backend.graph.store import GraphStore

QA_PROMPT = """Answer the question using only the code excerpts below. Cite the exact
file and line where each claim comes from, using the format path:line. If the answer
is not in the excerpts, say so.

Question: {question}

Excerpts:
{context}"""


def _chunk_ref(chunk) -> str:
    path = chunk.properties.get("path") or chunk.title
    start = chunk.properties.get("start_line", 1)
    return f"{path}:{start}"


def ask_repo(
    store: GraphStore,
    owner: str,
    repo: str,
    question: str,
    *,
    top_k: int = 5,
    provider: LLMProvider | None = None,
    embedder: LLMProvider | None = None,
) -> str:
    provider = provider or get_provider()
    embedder = embedder or get_embedder()

    repo_nodes = [n for n in store.list_nodes(type="repo") if n.title == f"{owner}/{repo}"]
    if not repo_nodes:
        raise ValueError(f"repo not indexed: {owner}/{repo}")
    repo_id = repo_nodes[0].id

    embedding = embedder.embed([question])[0]
    results = store.search(embedding, top_k=top_k, node_type="chunk")
    chunks = [node for node, _ in results if node.properties.get("repo") == repo_id]
    if not chunks:
        raise ValueError(f"no indexed chunks for {owner}/{repo}")

    context = "\n\n".join(f"--- {_chunk_ref(node)} ---\n{node.summary}" for node in chunks)
    answer = provider.chat(
        [ChatMessage(role="user", content=QA_PROMPT.format(question=question, context=context))]
    )
    return answer
