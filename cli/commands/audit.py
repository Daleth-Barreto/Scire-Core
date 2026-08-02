import httpx
import typer

from backend.graph.db import session_scope
from backend.graph.store import GraphStore
from backend.repos.audit import audit_paper


def audit_cmd(
    paper: str,
    repo: str,
    top_k: int = typer.Option(5, "--top-k", min=1, max=20),
) -> None:
    owner, sep, name = repo.partition("/")
    if not sep:
        raise typer.BadParameter("repo must be owner/name, e.g. psf/requests")

    try:
        with session_scope() as session:
            report = audit_paper(GraphStore(session), paper, owner, name, top_k=top_k)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    except (httpx.HTTPError, NotImplementedError) as exc:
        raise typer.BadParameter(f"audit failed: {exc}") from exc

    summary = report.summary()
    typer.echo(
        f"audit: {report.paper_title} vs {report.repo} "
        f"({summary['supported']} supported, {summary['refuted']} refuted, "
        f"{summary['not-evidenced']} not-evidenced)"
    )
    for verdict in report.verdicts:
        tag = {"supported": "OK", "refuted": "REFUTED", "not-evidenced": "NO EVIDENCE"}.get(
            verdict.verdict, "?"
        )
        typer.echo(f"  [{tag}] {verdict.claim}")
        if verdict.evidence:
            typer.echo(f"        {verdict.evidence}")
        if verdict.reason:
            typer.echo(f"        {verdict.reason}")
