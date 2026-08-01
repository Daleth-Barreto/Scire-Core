import typer

from backend.core.config import get_settings
from backend.graph.db import session_scope
from backend.graph.store import GraphStore
from backend.repos.github import GitHubAdapter
from backend.repos.index import RepoIndexer

repo_app = typer.Typer(help="GitHub repository analysis.")


def _split_owner_repo(owner_repo: str) -> tuple[str, str]:
    parts = owner_repo.split("/")
    if len(parts) != 2 or not all(parts):
        raise typer.BadParameter("expected owner/name, e.g. anomalyco/opencode")
    return parts[0], parts[1]


@repo_app.command("add")
def repo_add(
    owner_repo: str,
    limit_files: int = typer.Option(200, "--limit-files", min=1, max=1000),
) -> None:
    owner, repo = _split_owner_repo(owner_repo)
    token = get_settings().github_token.get_secret_value()
    adapter = GitHubAdapter(token=token)
    with session_scope() as session:
        from backend.memory.actions import log_action

        store = GraphStore(session)
        indexer = RepoIndexer(store, adapter)
        counts = indexer.add_repo(owner, repo, limit_files=limit_files)
        log_action(store, "repo_add", target_id=counts["repo_id"], details=f"{owner}/{repo}")
        typer.echo(f"indexed {owner}/{repo}: {counts}")


@repo_app.command("ask")
def repo_ask(
    owner_repo: str,
    question: str,
    top_k: int = typer.Option(5, "--top-k", min=1, max=20),
) -> None:
    owner, repo = _split_owner_repo(owner_repo)
    with session_scope() as session:
        from backend.repos.qa import ask_repo

        try:
            answer = ask_repo(GraphStore(session), owner, repo, question, top_k=top_k)
        except ValueError as exc:
            raise typer.BadParameter(str(exc)) from exc
        typer.echo(answer)
