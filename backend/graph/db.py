from contextlib import contextmanager
from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker


@lru_cache
def get_engine(url: str | None = None) -> Engine:
    from backend.core.config import get_settings

    return create_engine(url or get_settings().database_url)


def get_session_factory(url: str | None = None) -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(url), autoflush=False, expire_on_commit=False)


def get_session(url: str | None = None) -> Session:
    factory = get_session_factory(url)
    session = factory()
    return session


@contextmanager
def session_scope(url: str | None = None):
    session = get_session(url)
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
