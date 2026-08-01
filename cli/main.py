import sys

import typer

from backend.core.config import get_settings
from cli.commands.config import config_app
from cli.commands.graph import edge_app, graph_app, node_app
from cli.commands.ingest import ingest_app
from cli.commands.notes import note_app
from cli.commands.repos import repo_app
from cli.commands.search import paper_app, search_cmd
from cli.commands.shell import shell_cmd

app = typer.Typer(name="scire", help="AI research copilot.")

app.command("search")(search_cmd)
app.command("shell")(shell_cmd)
app.add_typer(config_app, name="config")
app.add_typer(note_app, name="note")
app.add_typer(node_app, name="node")
app.add_typer(edge_app, name="edge")
app.add_typer(graph_app, name="graph")
app.add_typer(ingest_app, name="ingest")
app.add_typer(paper_app, name="paper")
app.add_typer(repo_app, name="repo")


def _force_utf8_streams() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, ValueError):
            pass


@app.callback()
def main() -> None:
    _force_utf8_streams()


@app.command()
def whoami() -> None:
    settings = get_settings()
    provider = settings.llm_provider
    try:
        _key = settings.provider_api_key
        key_status = "set"
    except ValueError:
        key_status = "missing"
    typer.echo(f"provider: {provider}")
    typer.echo(f"api key: {key_status}")


@app.command()
def chat(prompt: str, model: str | None = None) -> None:
    from backend.core.providers import ChatMessage, get_provider

    try:
        provider = get_provider()
        reply = provider.chat([ChatMessage(role="user", content=prompt)], model=model)
    except ValueError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc
    typer.echo(reply)


if __name__ == "__main__":
    app()
