import httpx
import typer

from backend.graph.db import session_scope
from backend.graph.store import GraphStore
from backend.search.arxiv import ArxivAdapter
from backend.search.base import CandidateNode, SearchAdapter
from backend.search.duckduckgo import DuckDuckGoAdapter
from backend.search.openalex import OpenAlexAdapter
from backend.search.semantic_scholar import SemanticScholarAdapter

paper_app = typer.Typer(help="Fetch a specific paper.")

FETCH_ADAPTERS: dict[str, type[SearchAdapter]] = {
    "arxiv": ArxivAdapter,
    "ss": SemanticScholarAdapter,
    "semanticscholar": SemanticScholarAdapter,
    "oa": OpenAlexAdapter,
    "openalex": OpenAlexAdapter,
}


def _search_adapters() -> list[SearchAdapter]:
    return [ArxivAdapter(), OpenAlexAdapter(), SemanticScholarAdapter(), DuckDuckGoAdapter()]


def _persist(store: GraphStore, candidates: list[CandidateNode], action: str = "persist") -> None:
    from backend.memory.actions import log_action
    from backend.search.persist import persist_candidates

    counts = persist_candidates(store, candidates)
    target_id = counts["paper_ids"][0] if counts["paper_ids"] else None
    log_action(store, action, target_id=target_id, details="; ".join(c.title for c in candidates))
    typer.echo(f"persisted {counts['papers']} papers, {counts['authors']} authors")


def search_cmd(
    query: str,
    limit: int = typer.Option(10, "--limit", "-n", min=1, max=50),
    persist: str | None = typer.Option(
        None, "--persist", help="Persist candidates: 'all' or comma-separated indices"
    ),
) -> None:
    candidates: list[CandidateNode] = []
    seen: set[tuple[str, str]] = set()
    for adapter in _search_adapters():
        try:
            for cand in adapter.search(query, limit=limit):
                key = (cand.source, cand.external_id)
                if key not in seen:
                    seen.add(key)
                    candidates.append(cand)
        except httpx.HTTPError as exc:
            typer.echo(f"warning: {type(adapter).__name__} failed: {exc}", err=True)

    if not candidates:
        typer.echo("no results")
        return
    for i, cand in enumerate(candidates):
        typer.echo(f"[{i}] ({cand.source}) {cand.title}")
        if cand.authors:
            typer.echo(f"    {', '.join(cand.authors[:5])}")
        if cand.published:
            typer.echo(f"    published {cand.published}  {cand.url}")

    if persist:
        indices = (
            list(range(len(candidates)))
            if persist == "all"
            else [int(part) for part in persist.split(",") if part.strip()]
        )
        invalid = [i for i in indices if i < 0 or i >= len(candidates)]
        if invalid:
            raise typer.BadParameter(f"index out of range: {invalid}")
        selected = [candidates[i] for i in indices]
        with session_scope() as session:
            _persist(GraphStore(session), selected, action="search")


@paper_app.command("fetch")
def fetch_cmd(
    external_id: str,
    persist: bool = typer.Option(True, "--persist/--no-persist"),
) -> None:
    source, sep, value = external_id.partition(":")
    if not sep or source not in FETCH_ADAPTERS:
        raise typer.BadParameter("expected format <arxiv|ss>:<id>, e.g. arxiv:2301.00000")
    adapter_cls = FETCH_ADAPTERS[source]
    adapter = adapter_cls()  # type: ignore[operator]
    try:
        candidate = adapter.fetch(value)
    except httpx.HTTPError as exc:
        raise typer.BadParameter(f"fetch failed: {exc}") from exc
    if candidate is None:
        typer.echo(f"not found: {external_id}")
        raise typer.Exit()
    typer.echo(f"({candidate.source}) {candidate.title}")
    typer.echo(f"    {', '.join(candidate.authors[:5])}")
    typer.echo(f"    {candidate.published or 'n/a'}  {candidate.url}")
    if candidate.summary:
        typer.echo(f"\n{candidate.summary[:500]}")
    if persist:
        with session_scope() as session:
            _persist(GraphStore(session), [candidate], action="fetch")
