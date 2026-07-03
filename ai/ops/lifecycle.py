import json
import os
from collections import deque
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

DATA_DIR = Path(os.getenv("HARNESS_DATA_DIR", "data"))
OPS_LOG = DATA_DIR / "ops.jsonl"
RECENT_LIMIT = int(os.getenv("OPS_RECENT_LIMIT", "500"))
FILE_READ_LIMIT = int(os.getenv("OPS_FILE_READ_LIMIT", "2000"))


class Lifecycle:
    RECEIVED = "received"
    PROCESSING = "processing"
    REPLIED = "replied"
    HANDED_OFF = "handed_off"
    BOT_RESUMED = "bot_resumed"
    IGNORED = "ignored"
    FAILED = "failed"
    DUPLICATE = "duplicate"
    WEBHOOK_IGNORED = "webhook_ignored"


STATUS_LABELS: dict[str, str] = {
    Lifecycle.RECEIVED: "Mensagem recebida",
    Lifecycle.PROCESSING: "Processando",
    Lifecycle.REPLIED: "Resposta enviada",
    Lifecycle.HANDED_OFF: "Encaminhado para humano",
    Lifecycle.BOT_RESUMED: "Bot reativado",
    Lifecycle.IGNORED: "Ignorado",
    Lifecycle.FAILED: "Falha",
    Lifecycle.DUPLICATE: "Duplicado",
    Lifecycle.WEBHOOK_IGNORED: "Webhook ignorado",
}

DIRECTION_BY_STATUS: dict[str, str] = {
    Lifecycle.RECEIVED: "inbound",
    Lifecycle.REPLIED: "outbound",
    Lifecycle.PROCESSING: "system",
    Lifecycle.HANDED_OFF: "system",
    Lifecycle.BOT_RESUMED: "system",
    Lifecycle.IGNORED: "system",
    Lifecycle.FAILED: "system",
    Lifecycle.DUPLICATE: "system",
    Lifecycle.WEBHOOK_IGNORED: "system",
}

IGNORED_REASON_LABELS: dict[str, str] = {
    "not_message_created": "Evento não é mensagem nova",
    "not_incoming": "Não é mensagem do cliente",
    "conversation_open_human_active": "Atendente humano ativo",
    "empty_content": "Mensagem vazia",
    "missing_conversation_or_account": "Sem conversa ou account no payload",
    "sender_not_contact": "Remetente não é o contato",
    "plan_limit_exceeded": "Limite do plano excedido",
}

_recent: deque[dict] = deque(maxlen=RECENT_LIMIT)


@dataclass
class OpsEvent:
    ts: str
    delivery_id: str
    message_id: str
    conversation_id: int
    status: str
    detail: str
    tenant_id: str = ""
    account_id: int | None = None
    inbox_id: int | None = None
    direction: str = "system"


def _event_key(event: dict) -> str:
    return "|".join(
        [
            event.get("ts", ""),
            str(event.get("message_id", "")),
            event.get("status", ""),
            str(event.get("conversation_id", "")),
        ]
    )


def _normalize_event(raw: dict) -> dict:
    status = str(raw.get("status", ""))
    direction = raw.get("direction") or DIRECTION_BY_STATUS.get(status, "system")
    detail = str(raw.get("detail", ""))
    label = STATUS_LABELS.get(status, status)
    if status in {Lifecycle.IGNORED, Lifecycle.WEBHOOK_IGNORED} and detail in IGNORED_REASON_LABELS:
        label = f"{label}: {IGNORED_REASON_LABELS[detail]}"

    return {
        "ts": raw.get("ts", ""),
        "delivery_id": raw.get("delivery_id", ""),
        "message_id": str(raw.get("message_id", "")),
        "conversation_id": int(raw.get("conversation_id") or 0),
        "status": status,
        "detail": detail,
        "tenant_id": raw.get("tenant_id") or "",
        "account_id": raw.get("account_id"),
        "inbox_id": raw.get("inbox_id"),
        "direction": direction,
        "label": label,
    }


def record_event(
    *,
    delivery_id: str,
    message_id: str,
    conversation_id: int,
    status: str,
    detail: str = "",
    tenant_id: str = "",
    account_id: int | None = None,
    inbox_id: int | None = None,
    direction: str | None = None,
) -> None:
    event = OpsEvent(
        ts=datetime.now(UTC).isoformat(),
        delivery_id=delivery_id,
        message_id=message_id,
        conversation_id=conversation_id,
        status=status,
        detail=detail,
        tenant_id=tenant_id,
        account_id=account_id,
        inbox_id=inbox_id,
        direction=direction or DIRECTION_BY_STATUS.get(status, "system"),
    )
    payload = asdict(event)
    _recent.appendleft(payload)

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with OPS_LOG.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _read_file_events(limit: int) -> list[dict]:
    if not OPS_LOG.is_file():
        return []

    lines: list[str] = []
    with OPS_LOG.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                lines.append(line)

    tail = lines[-FILE_READ_LIMIT:]
    events: list[dict] = []
    for line in reversed(tail):
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
        if len(events) >= limit:
            break
    return events


def list_events(
    *,
    limit: int = 20,
    offset: int = 0,
    tenant_id: str | None = None,
) -> tuple[list[dict], int]:
    merged: dict[str, dict] = {}
    for raw in list(_recent) + _read_file_events(FILE_READ_LIMIT):
        normalized = _normalize_event(raw)
        merged[_event_key(normalized)] = normalized

    events = sorted(merged.values(), key=lambda item: item["ts"], reverse=True)
    if tenant_id:
        events = [event for event in events if event.get("tenant_id") == tenant_id]
    total = len(events)
    return events[offset : offset + limit], total


def recent_events(limit: int = 50) -> list[dict]:
    events, _ = list_events(limit=limit, offset=0)
    return events
