from dataclasses import dataclass
from pathlib import Path

import psycopg
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from backend.graph.db import get_engine
from backend.graph.models import Base

DEFAULT_DB_NAME = "scire"
DEFAULT_DB_USER = "scire"
DEFAULT_DB_PASSWORD = "scire"


@dataclass
class InitResult:
    env_created: bool
    env_existed: bool
    role_status: str
    db_status: str
    vector_status: str
    tables_ready: bool
    admin_url_supplied: bool


def write_env_file(project_dir: Path) -> bool:
    example = project_dir / ".env.example"
    if not example.exists():
        raise FileNotFoundError(f"missing {example} — run init from the project root")
    env = project_dir / ".env"
    if env.exists():
        return False
    env.write_text(example.read_text(encoding="utf-8"), encoding="utf-8")
    return True


def _admin_conn(admin_url: str):
    url = admin_url.replace("postgresql+psycopg://", "postgresql://")
    return psycopg.connect(url, autocommit=True)


def _ensure_database(
    admin_url: str,
    db_name: str = DEFAULT_DB_NAME,
    db_user: str = DEFAULT_DB_USER,
    db_password: str = DEFAULT_DB_PASSWORD,
) -> tuple[str, str, str]:
    with _admin_conn(admin_url) as conn:
        role_exists = conn.execute(
            "SELECT 1 FROM pg_roles WHERE rolname = %s", (db_user,)
        ).fetchone()
        if role_exists:
            role_status = "exists"
        else:
            conn.execute(
                f"CREATE ROLE {db_user} LOGIN PASSWORD %s",
                (db_password,),
            )
            role_status = "created"

        db_exists = conn.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s", (db_name,)
        ).fetchone()
        if db_exists:
            db_status = "exists"
        else:
            conn.execute(f"CREATE DATABASE {db_name} OWNER {db_user}")
            db_status = "created"

    db_url, _, _ = admin_url.rpartition("/")
    with _admin_conn(f"{db_url}/{db_name}") as conn:
        vector_exists = conn.execute(
            "SELECT 1 FROM pg_extension WHERE extname = 'vector'"
        ).fetchone()
        if vector_exists:
            vector_status = "exists"
        else:
            conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
            vector_status = "created"

    return role_status, db_status, vector_status


def _create_tables(project_dir: Path, database_url: str | None) -> None:
    Base.metadata.create_all(get_engine(database_url))


def _graph_ready(project_dir: Path, database_url: str | None = None) -> bool:
    try:
        engine = get_engine(database_url)
        with engine.connect() as conn:
            return conn.execute(text("SELECT to_regclass('public.nodes') IS NOT NULL")).scalar()
    except SQLAlchemyError:
        return False


def run_init(
    project_dir: Path,
    admin_url: str | None = None,
    database_url: str | None = None,
) -> InitResult:
    env_existed = (project_dir / ".env").exists()
    env_created = write_env_file(project_dir)

    role_status = db_status = vector_status = "skipped"
    if admin_url:
        db_name = DEFAULT_DB_NAME
        if database_url:
            db_name = database_url.rpartition("/")[2].split("?")[0]
        role_status, db_status, vector_status = _ensure_database(admin_url, db_name=db_name)

    _create_tables(project_dir, database_url)
    tables_ready = _graph_ready(project_dir, database_url)

    return InitResult(
        env_created=env_created,
        env_existed=env_existed,
        role_status=role_status,
        db_status=db_status,
        vector_status=vector_status,
        tables_ready=tables_ready,
        admin_url_supplied=admin_url is not None,
    )
