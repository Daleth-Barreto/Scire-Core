from pathlib import Path
from typing import Annotated

import httpx
import typer

from backend.research.deepresearch import deepresearch


def deepresearch_cmd(
    topic: str,
    limit: Annotated[int, typer.Option("--limit", "-n", min=1, max=20)] = 5,
    save: Annotated[Path | None, typer.Option("--save", "-o", help="Save brief to a markdown file")] = None,
) -> None:
    try:
        brief = deepresearch(topic, limit=limit)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    except httpx.HTTPError as exc:
        raise typer.BadParameter(f"deepresearch failed: {exc}") from exc

    typer.echo(brief.markdown)
    typer.echo(f"\n--- sources ({len(brief.sources)}) ---")
    for i, source in enumerate(brief.sources, start=1):
        typer.echo(f"[{i}] {source.title} — {source.url}")

    status = "verified" if brief.verified else "needs review"
    typer.echo(f"\nverdict: {status}")
    for issue in brief.issues:
        typer.echo(f"  ! {issue}")

    if save:
        save.write_text(brief.markdown, encoding="utf-8")
        typer.echo(f"saved {save}")
