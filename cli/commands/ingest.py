import json
from pathlib import Path

import typer

from backend.graph.db import session_scope
from backend.graph.store import GraphStore
from backend.ingest.chunker import chunk_text
from backend.ingest.parser import extract_text

ingest_app = typer.Typer(help="Document ingestion.")


@ingest_app.command("pdf")
def ingest_pdf(
    path: Path,
    title: str | None = typer.Option(None, "--title", help="Paper title"),
    extract_only: bool = typer.Option(
        False, "--extract-only", help="Print text and chunks, no LLM"
    ),
) -> None:
    if not path.is_file():
        raise typer.BadParameter(f"file not found: {path}")

    text = extract_text(path)
    chunks = chunk_text(text)
    if extract_only:
        typer.echo(f"pages: {len(text)} chars, {len(chunks)} chunks")
        for i, chunk in enumerate(chunks):
            typer.echo(f"\n--- chunk {i} ---\n{chunk}")
        return

    with session_scope() as session:
        store = GraphStore(session)
        from backend.ingest.pipeline import IngestPipeline
        from backend.memory.actions import log_action

        pipeline = IngestPipeline(store)
        counts = pipeline.ingest(path, title=title)
        log_action(store, "ingest", target_id=counts.get("paper_id"), details=str(path))
        typer.echo(f"ingested {path.name}: {json.dumps(counts)}")
