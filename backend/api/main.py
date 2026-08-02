import httpx
from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from backend.api.schemas import (
    CandidateOut,
    ChatIn,
    ConfigKeysIn,
    ConfigOut,
    ConfigUnlockIn,
    GraphOut,
    NoteIn,
    PaperFetchIn,
    RepoAddIn,
    RepoAskIn,
    SearchIn,
)
from backend.core.envfile import mask
from backend.graph.db import session_scope
from backend.graph.store import GraphStore
from backend.ingest.pipeline import IngestCounts

app = FastAPI(title="Scire API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/graph", response_model=GraphOut)
def graph_dump() -> GraphOut:
    with session_scope() as session:
        from backend.graph.json_export import export_graph

        data = export_graph(GraphStore(session))
    return GraphOut(**data)


@app.get("/api/graph/nodes/{node_id}")
def node_detail(node_id: str) -> dict:
    with session_scope() as session:
        store = GraphStore(session)
        node = store.get_node(node_id)
        if node is None:
            raise HTTPException(status_code=404, detail="node not found")
        neighbors = [
            {"id": n.id, "type": n.type, "title": n.title} for n in store.neighbors(node_id)
        ]
        return {
            "id": node.id,
            "type": node.type,
            "title": node.title,
            "summary": node.summary,
            "properties": node.properties,
            "neighbors": neighbors,
        }


@app.get("/api/graph/search")
def graph_search(
    q: str = Query(...),
    top_k: int = Query(10, ge=1, le=50),
    node_type: str | None = None,
) -> list[dict]:
    try:
        from backend.core.providers import get_embedder

        embedding = get_embedder().embed([q])[0]
    except (httpx.HTTPError, NotImplementedError, ValueError):
        raise HTTPException(status_code=503, detail="embedding unavailable")
    with session_scope() as session:
        results = GraphStore(session).search(embedding, top_k=top_k, node_type=node_type)
        return [
            {
                "id": node.id,
                "type": node.type,
                "title": node.title,
                "summary": node.summary,
                "distance": round(distance, 4),
            }
            for node, distance in results
        ]


@app.post("/api/ingest/pdf")
def ingest_pdf(
    file: UploadFile = File(...),  # noqa: B008
    title: str | None = Form(None),
) -> IngestCounts:
    import tempfile
    from pathlib import Path

    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="expected a .pdf file")

    suffix = Path(file.filename).suffix
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(file.file.read())
        tmp_path = tmp.name
    try:
        from backend.ingest.pipeline import IngestPipeline
        from backend.memory.actions import log_action

        with session_scope() as session:
            store = GraphStore(session)
            counts = IngestPipeline(store).ingest(tmp_path, title=title or None)
            log_action(store, "ingest", target_id=counts["paper_id"], details=file.filename)
        return counts
    finally:
        Path(tmp_path).unlink(missing_ok=True)


@app.post("/api/papers/fetch", response_model=CandidateOut)
def paper_fetch(body: PaperFetchIn) -> CandidateOut:
    source, sep, value = body.external_id.partition(":")
    adapters = {
        "arxiv": "backend.search.arxiv.ArxivAdapter",
        "ss": "backend.search.semantic_scholar.SemanticScholarAdapter",
        "semanticscholar": "backend.search.semantic_scholar.SemanticScholarAdapter",
        "oa": "backend.search.openalex.OpenAlexAdapter",
        "openalex": "backend.search.openalex.OpenAlexAdapter",
        "epmc": "backend.search.europepmc.EuropePMCAdapter",
        "europepmc": "backend.search.europepmc.EuropePMCAdapter",
    }
    if not sep or source not in adapters:
        raise HTTPException(status_code=400, detail="expected <arxiv|ss>:<id>")
    from importlib import import_module

    module_name, class_name = adapters[source].rsplit(".", 1)
    adapter = getattr(import_module(module_name), class_name)()
    try:
        candidate = adapter.fetch(value)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    if candidate is None:
        raise HTTPException(status_code=404, detail="paper not found")

    if body.persist:
        from backend.memory.actions import log_action
        from backend.search.persist import persist_candidates

        with session_scope() as session:
            store = GraphStore(session)
            counts = persist_candidates(store, [candidate])
            target_id = counts["paper_ids"][0] if counts["paper_ids"] else None
            log_action(store, "fetch", target_id=target_id, details=candidate.title)
    return CandidateOut(**candidate.model_dump())


@app.post("/api/graph/gaps")
def graph_gaps() -> list[str]:
    with session_scope() as session:
        from backend.memory.gaps import detect_gaps

        return detect_gaps(GraphStore(session))


@app.post("/api/search", response_model=list[CandidateOut])
def search(body: SearchIn) -> list[CandidateOut]:
    from backend.search.arxiv import ArxivAdapter
    from backend.search.duckduckgo import DuckDuckGoAdapter
    from backend.search.europepmc import EuropePMCAdapter
    from backend.search.openalex import OpenAlexAdapter
    from backend.search.semantic_scholar import SemanticScholarAdapter

    candidates: list[CandidateOut] = []
    seen: set[tuple[str, str]] = set()
    for adapter in (
        ArxivAdapter(),
        OpenAlexAdapter(),
        SemanticScholarAdapter(),
        EuropePMCAdapter(),
        DuckDuckGoAdapter(),
    ):
        try:
            for cand in adapter.search(body.query, limit=body.limit):
                key = (cand.source, cand.external_id)
                if key not in seen:
                    seen.add(key)
                    candidates.append(CandidateOut(**cand.model_dump()))
        except httpx.HTTPError:
            continue

    if body.persist and candidates:
        from backend.memory.actions import log_action
        from backend.search.base import CandidateNode
        from backend.search.persist import persist_candidates

        with session_scope() as session:
            store = GraphStore(session)
            nodes = [CandidateNode(**c.model_dump()) for c in candidates]
            counts = persist_candidates(store, nodes)
            target_id = counts["paper_ids"][0] if counts["paper_ids"] else None
            log_action(
                store,
                "search",
                target_id=target_id,
                details="; ".join(c.title for c in candidates),
            )
    return candidates


@app.post("/api/repos/add")
def repo_add(body: RepoAddIn) -> dict[str, int | str]:
    from backend.core.config import get_settings
    from backend.memory.actions import log_action
    from backend.repos.github import GitHubAdapter
    from backend.repos.index import RepoCounts, RepoIndexer

    token = get_settings().effective_github_token().get_secret_value()
    adapter = GitHubAdapter(token=token)
    with session_scope() as session:
        store = GraphStore(session)
        indexer = RepoIndexer(store, adapter)
        try:
            counts: RepoCounts = indexer.add_repo(
                body.owner, body.repo, limit_files=body.limit_files
            )
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=502, detail=str(exc))
        log_action(
            store, "repo_add", target_id=counts["repo_id"], details=f"{body.owner}/{body.repo}"
        )
        return {
            "files": counts["files"],
            "chunks": counts["chunks"],
            "skipped": counts["skipped"],
            "repo_id": counts["repo_id"],
        }


@app.post("/api/repos/ask")
def repo_ask(body: RepoAskIn) -> dict[str, str]:
    with session_scope() as session:
        from backend.repos.qa import ask_repo

        try:
            answer = ask_repo(GraphStore(session), body.owner, body.repo, body.question)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        return {"answer": answer}


@app.get("/api/notes")
def list_notes() -> list[dict]:
    with session_scope() as session:
        from backend.memory.notes import list_notes

        return [
            {"id": n.id, "title": n.title, "summary": n.summary, "properties": n.properties}
            for n in list_notes(GraphStore(session))
        ]


@app.post("/api/notes")
def add_note(body: NoteIn) -> dict:
    with session_scope() as session:
        from backend.memory.notes import add_note

        node = add_note(GraphStore(session), body.content)
        return {"id": node.id, "title": node.title}


@app.post("/api/chat")
def chat(body: ChatIn) -> dict[str, str]:
    from backend.core.providers import ChatMessage, get_provider

    try:
        provider = get_provider()
        reply = provider.chat([ChatMessage(role="user", content=body.message)], model=body.model)
    except (ValueError, httpx.HTTPError) as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    with session_scope() as session:
        from backend.memory.actions import log_action

        log_action(GraphStore(session), "chat", details=body.message)
    return {"answer": reply}


@app.get("/api/config", response_model=ConfigOut)
def config() -> ConfigOut:
    from backend.core import secrets
    from backend.core.config import get_settings

    settings = get_settings()
    try:
        api_key = mask(settings.provider_api_key.get_secret_value())
    except ValueError:
        api_key = mask("")
    github_token = mask(settings.effective_github_token().get_secret_value())
    return ConfigOut(
        provider=settings.llm_provider,
        embed_model=settings.embed_model or None,
        api_key=api_key,
        github_token=github_token,
        encrypted=secrets.keys_path().exists(),
    )


@app.post("/api/config/keys")
def config_save_keys(body: ConfigKeysIn) -> dict[str, object]:
    from backend.core import secrets
    from backend.core.config import set_session_keys

    keys = {key: value for key, value in body.keys.items() if value}
    path = secrets.encrypt_keys(body.passphrase, keys)
    set_session_keys(keys)
    return {"status": "saved", "path": str(path), "keys": sorted(keys)}


@app.post("/api/config/unlock")
def config_unlock(body: ConfigUnlockIn) -> dict[str, object]:
    from backend.core import secrets
    from backend.core.config import set_session_keys

    try:
        keys = secrets.decrypt_keys(body.passphrase)
    except secrets.SecretStoreError as exc:
        raise HTTPException(status_code=401, detail=str(exc))
    set_session_keys(keys)
    return {"status": "unlocked", "keys": sorted(keys)}


@app.post("/api/config/lock")
def config_lock() -> dict[str, str]:
    from backend.core.config import clear_session_keys

    clear_session_keys()
    return {"status": "locked"}
