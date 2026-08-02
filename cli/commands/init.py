from pathlib import Path
from typing import Annotated

import typer

from backend.setup.init import run_init


def init_cmd(
    admin_url: Annotated[
        str | None,
        typer.Option(
            "--admin-url",
            help="Postgres admin URL (e.g. postgresql+psycopg://postgres:pass@localhost:5432/postgres) "
            "to auto-create role/db/pgvector. Omit to skip DB setup.",
        ),
    ] = None,
    database_url: Annotated[
        str | None,
        typer.Option("--database-url", help="Scire database URL (defaults to .env DATABASE_URL)."),
    ] = None,
) -> None:
    try:
        result = run_init(Path.cwd(), admin_url=admin_url, database_url=database_url)
    except FileNotFoundError as exc:
        raise typer.BadParameter(str(exc)) from exc

    if result.env_created:
        typer.echo(".env created from .env.example (edit it or run `scire config set`)")
    elif result.env_existed:
        typer.echo(".env already present — left untouched")

    if admin_url:
        typer.echo(f"database role: {result.role_status}")
        typer.echo(f"database: {result.db_status}")
        typer.echo(f"pgvector extension: {result.vector_status}")
    else:
        typer.echo("database setup skipped (pass --admin-url to auto-create role/db/pgvector)")

    if result.tables_ready:
        typer.echo("tables ready")
    else:
        typer.echo("tables: run `scire graph init` after configuring DATABASE_URL")

    typer.echo("done — run `scire whoami` to check provider/key status")
