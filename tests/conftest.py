import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from backend.core.cache import clear_caches
from backend.graph.db import get_session_factory
from backend.graph.models import EMBED_DIM, Base

TEST_DB_URL = "postgresql+psycopg://scire:scire@localhost:5432/scire_test"


@pytest.fixture(autouse=True)
def _clean_caches():
    clear_caches()
    yield
    clear_caches()


@pytest.fixture()
def session() -> Session:
    engine = create_engine(TEST_DB_URL)
    try:
        engine.connect()
    except OperationalError:
        pytest.skip("Postgres test DB not available")
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    factory = get_session_factory(TEST_DB_URL)
    with factory() as session:
        yield session
    Base.metadata.drop_all(engine)
    engine.dispose()


def make_embed(axis: int) -> list[float]:
    return [1.0 if i == axis else 0.0 for i in range(EMBED_DIM)]


@pytest.fixture
def fake_embedder(mocker):
    """Stub the embedder at every import site so tests never touch a real
    embed API and never depend on a configured key in .env."""
    embedder = mocker.MagicMock()
    embedder.embed.return_value = [make_embed(0)]
    mocker.patch("backend.memory.notes.get_embedder", return_value=embedder)
    mocker.patch("backend.search.persist.get_embedder", return_value=embedder)
    mocker.patch("backend.core.providers.get_embedder", return_value=embedder)
    return embedder
