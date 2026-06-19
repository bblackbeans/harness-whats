import json
import os
from collections import deque
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

DATA_DIR = Path(os.getenv("HARNESS_DATA_DIR", "data"))
OPS_LOG = DATA_DIR / "ops.jsonl"
RECENT_LIMIT = int(os.getenv("OPS_RECENT_LIMIT", "100"))

_recent: deque[dict] = deque(maxlen=RECENT_LIMIT)


class Lifecycle:
    RECEIVED = "received"
    PROCESSING = "processing"
    REPLIED = "replied"
    IGNORED = "ignored"
    FAILED = "failed"
    DUPLICATE = "duplicate"


@dataclass
class OpsEvent:
    ts: str
    delivery_id: str
    message_id: str
    conversation_id: int
    status: str
    detail: str


def record_event(
    *,
    delivery_id: str,
    message_id: str,
    conversation_id: int,
    status: str,
    detail: str = "",
) -> None:
    event = OpsEvent(
        ts=datetime.now(UTC).isoformat(),
        delivery_id=delivery_id,
        message_id=message_id,
        conversation_id=conversation_id,
        status=status,
        detail=detail,
    )
    payload = asdict(event)
    _recent.appendleft(payload)

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with OPS_LOG.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def recent_events(limit: int = 50) -> list[dict]:
    return list(_recent)[:limit]
