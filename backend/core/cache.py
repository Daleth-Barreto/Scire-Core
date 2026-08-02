import threading
import time
from collections import OrderedDict
from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar

F = TypeVar("F", bound=Callable[..., Any])


class TTLCache:
    """Thread-safe TTL cache with max-size LRU eviction."""

    def __init__(self, ttl: float = 300.0, maxsize: int = 256) -> None:
        self._ttl = ttl
        self._maxsize = maxsize
        self._data: OrderedDict[str, tuple[float, Any]] = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key: str) -> Any | None:
        with self._lock:
            item = self._data.get(key)
            if item is None:
                return None
            expires, value = item
            if time.monotonic() > expires:
                del self._data[key]
                return None
            self._data.move_to_end(key)
            return value

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            self._data[key] = (time.monotonic() + self._ttl, value)
            self._data.move_to_end(key)
            while len(self._data) > self._maxsize:
                self._data.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._data.clear()


_registry: dict[str, TTLCache] = {}
_registry_lock = threading.Lock()


def ttl_cache(ttl: float = 300.0, maxsize: int = 256) -> Callable[[F], F]:
    """Cache a method's return value by (qualname, args) across instances.

    ``self`` is excluded from the key so identical calls on different
    instances share one cache entry (useful for short-lived adapters).
    """

    def decorator(fn: F) -> F:
        cache = TTLCache(ttl=ttl, maxsize=maxsize)
        with _registry_lock:
            _registry[fn.__qualname__] = cache

        @wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            key_parts = [fn.__qualname__, repr(args[1:]), repr(kwargs)]
            key = ":".join(key_parts)
            hit = cache.get(key)
            if hit is not None:
                return hit
            value = fn(*args, **kwargs)
            cache.set(key, value)
            return value

        return wrapper  # type: ignore[return-value]

    return decorator


def clear_caches() -> None:
    with _registry_lock:
        for cache in _registry.values():
            cache.clear()
