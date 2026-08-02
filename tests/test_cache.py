import time

import pytest

from backend.core.cache import TTLCache, clear_caches, ttl_cache


@pytest.fixture(autouse=True)
def _clean_caches():
    clear_caches()
    yield
    clear_caches()


def test_ttl_cache_roundtrip():
    cache = TTLCache(ttl=60, maxsize=16)
    assert cache.get("k") is None
    cache.set("k", "v")
    assert cache.get("k") == "v"


def test_ttl_cache_expires():
    cache = TTLCache(ttl=0.05, maxsize=16)
    cache.set("k", "v")
    time.sleep(0.07)
    assert cache.get("k") is None


def test_ttl_cache_evicts_oldest_when_full():
    cache = TTLCache(ttl=60, maxsize=2)
    cache.set("a", 1)
    cache.set("b", 2)
    cache.set("c", 3)
    assert cache.get("a") is None
    assert cache.get("b") == 2
    assert cache.get("c") == 3


class _FakeAdapter:
    def __init__(self):
        self.calls = 0

    @ttl_cache(ttl=60)
    def search(self, query: str, limit: int = 10) -> list[str]:
        self.calls += 1
        return [f"{query}-{i}" for i in range(limit)]


def test_ttl_cache_decorator_caches_per_args():
    a = _FakeAdapter()
    assert a.search("gnn") == [f"gnn-{i}" for i in range(10)]
    assert a.search("gnn") == [f"gnn-{i}" for i in range(10)]
    assert a.calls == 1
    assert a.search("gnn", limit=2) == ["gnn-0", "gnn-1"]
    assert a.calls == 2


def test_ttl_cache_decorator_shared_across_instances():
    a, b = _FakeAdapter(), _FakeAdapter()
    a.search("same")
    b.search("same")
    assert a.calls + b.calls == 1


def test_ttl_cache_decorator_distinct_per_query():
    a = _FakeAdapter()
    a.search("one")
    a.search("two")
    assert a.calls == 2


def test_ttl_cache_clear_all():
    a = _FakeAdapter()
    a.search("x")
    clear_caches()
    a.search("x")
    assert a.calls == 2
