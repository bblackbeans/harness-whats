import hashlib
import hmac
import os
import re

import httpx

CHATWOOT_BASE_URL = os.getenv("CHATWOOT_BASE_URL", "").rstrip("/")
CHATWOOT_BOT_TOKEN = os.getenv("CHATWOOT_BOT_TOKEN", "")
CHATWOOT_ACCOUNT_ID = os.getenv("CHATWOOT_ACCOUNT_ID", "")
CHATWOOT_WEBHOOK_SECRET = os.getenv("CHATWOOT_WEBHOOK_SECRET", "")


def _headers() -> dict[str, str]:
    return {"api_access_token": CHATWOOT_BOT_TOKEN, "Content-Type": "application/json"}


def is_configured() -> bool:
    return bool(CHATWOOT_BASE_URL and CHATWOOT_BOT_TOKEN and CHATWOOT_ACCOUNT_ID)


def default_account_id() -> int:
    if not CHATWOOT_ACCOUNT_ID:
        raise ValueError("CHATWOOT_ACCOUNT_ID não configurado")
    return int(CHATWOOT_ACCOUNT_ID)


def normalize_phone(value: str) -> str:
    return re.sub(r"\D", "", value)


def verify_webhook_signature(body: bytes, signature: str | None, timestamp: str | None) -> bool:
    if not CHATWOOT_WEBHOOK_SECRET:
        return True
    if not signature or not timestamp:
        return False

    signed_payload = f"{timestamp}.{body.decode('utf-8')}".encode()
    expected = hmac.new(
        CHATWOOT_WEBHOOK_SECRET.encode(),
        signed_payload,
        hashlib.sha256,
    ).hexdigest()

    provided = signature.removeprefix("sha256=")
    return hmac.compare_digest(expected, provided)


def _account_id(payload: dict) -> int | None:
    account = payload.get("account")
    if isinstance(account, dict) and account.get("id") is not None:
        return int(account["id"])
    if CHATWOOT_ACCOUNT_ID:
        return int(CHATWOOT_ACCOUNT_ID)
    return None


def _conversation_id(payload: dict) -> int | None:
    conversation = payload.get("conversation")
    if isinstance(conversation, dict) and conversation.get("id") is not None:
        return int(conversation["id"])

    event = str(payload.get("event", "")).lower()
    if event.startswith("conversation") and payload.get("id") is not None:
        return int(payload["id"])

    return None


def _contact_phone(payload: dict) -> str:
    conversation = payload.get("conversation") or {}
    contact = payload.get("contact") or conversation.get("contact") or {}
    for key in ("phone_number", "identifier"):
        value = contact.get(key)
        if value:
            return normalize_phone(str(value))
    return ""


def _contact_name(payload: dict) -> str:
    conversation = payload.get("conversation") or {}
    contact = payload.get("contact") or conversation.get("contact") or {}
    return str(contact.get("name") or "")


def _message_type(payload: dict) -> str:
    message = payload.get("message")
    if isinstance(message, dict) and message.get("message_type"):
        return str(message["message_type"])
    return str(payload.get("message_type", ""))


def _message_content(payload: dict) -> str:
    message = payload.get("message")
    if isinstance(message, dict) and message.get("content"):
        return str(message["content"]).strip()
    return str(payload.get("content", "")).strip()


def _inbox_id(payload: dict) -> int | None:
    conversation = payload.get("conversation") or {}
    if conversation.get("inbox_id") is not None:
        return int(conversation["inbox_id"])

    if payload.get("inbox_id") is not None:
        return int(payload["inbox_id"])

    inbox = payload.get("inbox")
    if isinstance(inbox, dict) and inbox.get("id") is not None:
        return int(inbox["id"])

    return None


def _conversation_status(payload: dict) -> str:
    conversation = payload.get("conversation") or {}
    status = conversation.get("status", payload.get("status", ""))
    return str(status).lower()


def conversation_status(payload: dict) -> str:
    return _conversation_status(payload)


def ignore_reason(payload: dict) -> str | None:
    if str(payload.get("event", "")).lower() != "message_created":
        return "not_message_created"

    if _message_type(payload) != "incoming":
        return "not_incoming"

    status = _conversation_status(payload)
    if status == "open":
        return "conversation_open_human_active"

    content = _message_content(payload)
    if not content:
        return "empty_content"

    conversation_id = _conversation_id(payload)
    account_id = _account_id(payload)
    if conversation_id is None or account_id is None:
        return "missing_conversation_or_account"

    sender = payload.get("sender") or (payload.get("message") or {}).get("sender") or {}
    if str(sender.get("type", "")).lower() in {"user", "agent_bot"}:
        return "sender_not_contact"

    return None


def webhook_conversation_id(payload: dict) -> int | None:
    return _conversation_id(payload)


def webhook_account_id(payload: dict) -> int | None:
    return _account_id(payload)


def webhook_inbox_id(payload: dict) -> int | None:
    return _inbox_id(payload)


def webhook_message_id(payload: dict) -> str:
    message = payload.get("message") or {}
    return str(payload.get("id") or message.get("id") or "")


def is_conversation_status_webhook(payload: dict) -> bool:
    event = str(payload.get("event", "")).lower()
    return event in {"conversation_resolved", "conversation_status_changed"}


def should_resume_bot_on_resolve(payload: dict) -> bool:
    event = str(payload.get("event", "")).lower()
    status = _conversation_status(payload)

    if event == "conversation_resolved":
        return True

    if event == "conversation_status_changed" and status == "resolved":
        return True

    return False


def extract_inbound_message(payload: dict) -> dict | None:
    if ignore_reason(payload):
        return None

    content = _message_content(payload)
    conversation_id = _conversation_id(payload)
    account_id = _account_id(payload)
    message = payload.get("message") or {}
    message_id = str(payload.get("id") or message.get("id") or "")

    return {
        "phone": _contact_phone(payload),
        "contact_name": _contact_name(payload),
        "text": content,
        "conversation_id": conversation_id,
        "account_id": account_id,
        "inbox_id": _inbox_id(payload),
        "message_id": message_id,
        "conversation_status": _conversation_status(payload),
        "raw": payload,
    }


async def send_private_note(account_id: int, conversation_id: int, content: str) -> dict:
    if not CHATWOOT_BOT_TOKEN or not CHATWOOT_BASE_URL:
        return {"ok": False, "error": "Chatwoot não configurado"}

    url = (
        f"{CHATWOOT_BASE_URL}/api/v1/accounts/{account_id}"
        f"/conversations/{conversation_id}/messages"
    )
    payload = {"content": content, "message_type": "outgoing", "private": True}

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(url, json=payload, headers=_headers())
        if response.status_code >= 400:
            return {"ok": False, "error": response.text, "status": response.status_code}
        return {"ok": True, "data": response.json()}


async def handoff_conversation(account_id: int, conversation_id: int) -> dict:
    if not CHATWOOT_BOT_TOKEN or not CHATWOOT_BASE_URL:
        return {"ok": False, "error": "Chatwoot não configurado"}

    url = (
        f"{CHATWOOT_BASE_URL}/api/v1/accounts/{account_id}"
        f"/conversations/{conversation_id}/toggle_status"
    )
    payload = {"status": "open"}

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(url, json=payload, headers=_headers())
        if response.status_code >= 400:
            return {"ok": False, "error": response.text, "status": response.status_code}
        return {"ok": True, "data": response.json()}


async def resume_bot_conversation(account_id: int, conversation_id: int) -> dict:
    """Devolve a conversa ao Agent Bot (status pending) na mesma thread."""
    if not CHATWOOT_BOT_TOKEN or not CHATWOOT_BASE_URL:
        return {"ok": False, "error": "Chatwoot não configurado"}

    url = (
        f"{CHATWOOT_BASE_URL}/api/v1/accounts/{account_id}"
        f"/conversations/{conversation_id}/toggle_status"
    )
    payload = {"status": "pending"}

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(url, json=payload, headers=_headers())
        if response.status_code >= 400:
            return {"ok": False, "error": response.text, "status": response.status_code}
        return {"ok": True, "data": response.json()}


async def send_message(account_id: int, conversation_id: int, content: str) -> dict:
    if not CHATWOOT_BOT_TOKEN or not CHATWOOT_BASE_URL:
        return {"ok": False, "error": "Chatwoot não configurado"}

    url = (
        f"{CHATWOOT_BASE_URL}/api/v1/accounts/{account_id}"
        f"/conversations/{conversation_id}/messages"
    )
    payload = {"content": content, "message_type": "outgoing", "private": False}

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(url, json=payload, headers=_headers())
        if response.status_code >= 400:
            return {"ok": False, "error": response.text, "status": response.status_code}
        return {"ok": True, "data": response.json()}


async def send_template(
    account_id: int,
    conversation_id: int,
    template_name: str,
    language: str,
    processed_params: dict,
    content: str = "",
) -> dict:
    if not CHATWOOT_BOT_TOKEN or not CHATWOOT_BASE_URL:
        return {"ok": False, "error": "Chatwoot não configurado"}

    url = (
        f"{CHATWOOT_BASE_URL}/api/v1/accounts/{account_id}"
        f"/conversations/{conversation_id}/messages"
    )
    payload = {
        "content": content or template_name,
        "message_type": "outgoing",
        "private": False,
        "template_params": {
            "name": template_name,
            "language": language,
            "processed_params": processed_params,
        },
    }

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(url, json=payload, headers=_headers())
        if response.status_code >= 400:
            return {"ok": False, "error": response.text, "status": response.status_code}
        return {"ok": True, "data": response.json()}
