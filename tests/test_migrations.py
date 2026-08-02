import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import OperationalError

from backend.graph.models import Base

TEST_DB_URL = "postgresql+psycopg://scire:scire@localhost:5432/scire_test"


def _alembic_config() -> Config:
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", TEST_DB_URL)
    return cfg


@pytest.fixture()
def empty_db():
    engine = create_engine(TEST_DB_URL)
    try:
        engine.connect()
    except OperationalError:
        pytest.skip("Postgres test DB not available")
    Base.metadata.drop_all(engine)
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS alembic_version"))
    yield engine
    Base.metadata.drop_all(engine)
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS alembic_version"))
    engine.dispose()


def test_upgrade_head_creates_schema(empty_db):
    command.upgrade(_alembic_config(), "head")

    tables = sorted(inspect(empty_db).get_table_names())
    assert tables == ["alembic_version", "edges", "nodes"]

    with empty_db.connect() as conn:
        version = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
    assert version == "322751a0bb42"


def test_upgrade_head_is_idempotent(empty_db):
    command.upgrade(_alembic_config(), "head")
    command.upgrade(_alembic_config(), "head")

    tables = sorted(inspect(empty_db).get_table_names())
    assert tables == ["alembic_version", "edges", "nodes"]


def test_stamp_head_marks_existing_schema(empty_db):
    Base.metadata.create_all(empty_db)
    command.stamp(_alembic_config(), "head")

    with empty_db.connect() as conn:
        version = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
    assert version == "322751a0bb42"
