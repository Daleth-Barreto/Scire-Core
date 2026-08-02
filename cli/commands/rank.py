import httpx
import typer

from backend.core.providers import get_embedder
from backend.graph.db import session_scope
from backend.graph.rank import rank_papers
from backend.graph.store import GraphStore


def rank_cmd(
    topic: str,
    limit: int = typer.Option(10, "--limit", "-n", min=1, max=50),
) -> None:
    try:
        embedding = get_embedder().embed([topic])[0]
    except (ValueError, NotImplementedError, httpx.HTTPError) as exc:
        raise typer.BadParameter(f"cannot embed query: {exc}") from exc

    with session_scope() as session:
        results = rank_papers(GraphStore(session), embedding, top_k=limit)

    if not results:
        typer.echo("no papers in graph matching topic")
        return

    typer.echo(f"{'score':>6}  {'rel':>4}  {'cit':>4}  {'met':>4}  {'pro':>4}  title")
    for paper in results:
        typer.echo(
            f"{paper.score:>6.3f}  {paper.relevance:>4.2f}  {paper.citations:>4.2f}  "
            f"{paper.method:>4.2f}  {paper.provenance:>4.2f}  {paper.node.title[:60]}"
        )
