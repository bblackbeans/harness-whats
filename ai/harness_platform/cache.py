import time
from threading import Lock
from typing import Any

_CACHE: dict[str, tuple[Any, float]] = {}
_LOCK = Lock()
TTL_SECONDS = 60


def get_cached(tenant_id: str) -> Any | None:
    with _LOCK:
        entry = _CACHE.get(tenant_id)
        if not entry:
            return None
        config, expires = entry
        if time.time() > expires:
            del _CACHE[tenant_id]
            return None
        return config


def set_cached(tenant_id: str, config: Any) -> None:
    with _LOCK:
        _CACHE[tenant_id] = (config, time.time() + TTL_SECONDS)


def invalidate_tenant_cache(tenant_id: str | None = None) -> None:
    with _LOCK:
        if tenant_id is None:
            _CACHE.clear()
        elif tenant_id in _CACHE:
            del _CACHE[tenant_id]
