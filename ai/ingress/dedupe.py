import time

TTL_SECONDS = 60 * 60 * 24

_seen: dict[str, float] = {}


def is_duplicate(delivery_id: str) -> bool:
    if not delivery_id:
        return False

    now = time.time()
    _prune(now)

    if delivery_id in _seen:
        return True

    _seen[delivery_id] = now
    return False


def _prune(now: float) -> None:
    expired = [key for key, ts in _seen.items() if now - ts > TTL_SECONDS]
    for key in expired:
        del _seen[key]
