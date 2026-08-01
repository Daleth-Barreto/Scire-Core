import typer

from backend.graph.db import session_scope
from backend.graph.store import GraphStore
from backend.memory.notes import add_note, list_notes

note_app = typer.Typer(help="Personal notes in the graph.")


@note_app.command("add")
def note_add(
    text: str,
    context_id: str | None = typer.Option(None, "--context", help="Tie this note to a node id"),
) -> None:
    with session_scope() as session:
        node = add_note(GraphStore(session), text, context_id=context_id)
        typer.echo(f"note saved {node.id}")


@note_app.command("list")
def note_list() -> None:
    with session_scope() as session:
        notes = list_notes(GraphStore(session))
        if not notes:
            typer.echo("no notes")
            return
        for note in notes:
            context = note.properties.get("context_id") or "-"
            typer.echo(f"{note.id}  context={context}\n    {note.summary}")
