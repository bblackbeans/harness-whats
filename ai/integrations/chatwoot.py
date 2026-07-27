import hashlib
import hmac
import os
import re

import httpx

from handoff.constants import HANDOFF_FLAG_ATTR

CHATWOOT_BASE_URL = os.getenv("CHATWOOT_BASE_URL", "").rstrip("/")
CHATWOOT_BOT_TOKEN = os.getenv("CHATWOOT_BOT_TOKEN", "")
CHATWOOT_ACCOUNT_ID = os.getenv("CHATWOOT_ACCOUNT_ID", "")
CHATWOOT_WEBHOOK_SECRET = os.getenv("CHATWOOT_WEBHOOK_SECRET", "")


def _headers(bot_token: str | None = None) -> dict[str, str]:
    token = (bot_token or "").strip() or CHATWOOT_BOT_TOKEN
    return {"api_access_token": token, "Content-Type": "application/json"}


def _admin_token() -> str:
    return os.getenv("CHATWOOT_ADMIN_TOKEN", "").strip()


def _token_for_account_labels(bot_token: str | None = None) -> str:
    """Token de usuário admin — bot não pode criar/listar etiquetas da conta."""
    return _admin_token() or (bot_token or "").strip() or CHATWOOT_BOT_TOKEN


def _is_token_configured(bot_token: str | None = None) -> bool:
    return bool(CHATWOOT_BASE_URL and ((bot_token or "").strip() or CHATWOOT_BOT_TOKEN))


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


def _contact_blobs(payload: dict) -> list[dict]:
    """Coleta objetos de contato/sender em vários formatos do webhook Chatwoot."""
    conversation = payload.get("conversation") or {}
    meta = conversation.get("meta") if isinstance(conversation.get("meta"), dict) else {}
    message = payload.get("message") if isinstance(payload.get("message"), dict) else {}
    blobs: list[dict] = []
    for item in (
        payload.get("contact"),
        conversation.get("contact"),
        payload.get("sender"),
        message.get("sender"),
        meta.get("sender"),
    ):
        if isinstance(item, dict) and item:
            blobs.append(item)
    return blobs


def _contact_chatwoot_id(payload: dict) -> int | None:
    for blob in _contact_blobs(payload):
        if blob.get("id") is not None:
            try:
                return int(blob["id"])
            except (TypeError, ValueError):
                continue
    return None


def _digits(value: object) -> str:
    return normalize_phone(str(value)) if value else ""


def _looks_like_whatsapp_jid(value: str) -> bool:
    lower = value.lower()
    return "@s.whatsapp.net" in lower or "@c.us" in lower or "@g.us" in lower


def _looks_like_e164_phone(digits: str) -> bool:
    """Heurística: telefone internacional (10–15 dígitos), não ID curto de rede social."""
    return 10 <= len(digits) <= 15


def _phone_from_blob(blob: dict) -> str:
    """Extrai telefone real quando o canal envia (WhatsApp). Telegram em geral não tem."""
    attrs = blob.get("additional_attributes") if isinstance(blob.get("additional_attributes"), dict) else {}
    custom = blob.get("custom_attributes") if isinstance(blob.get("custom_attributes"), dict) else {}

    # 1) Campos explícitos de telefone
    for value in (
        blob.get("phone_number"),
        attrs.get("phone_number"),
        attrs.get("phone"),
        attrs.get("whatsapp_id"),
        custom.get("phone_number"),
        custom.get("phone"),
        custom.get("telefone"),
    ):
        digits = _digits(value)
        if len(digits) >= 8:
            return digits

    # 2) Identifier só se for claramente WhatsApp / E.164
    for value in (blob.get("identifier"), blob.get("source_id"), attrs.get("id")):
        if not value:
            continue
        text = str(value)
        digits = _digits(text)
        if _looks_like_whatsapp_jid(text) and len(digits) >= 8:
            return digits
        if _looks_like_e164_phone(digits) and (
            text.strip().startswith("+") or digits.startswith("55") or len(digits) >= 11
        ):
            return digits
    return ""


def _channel_identity_from_blob(blob: dict) -> str:
    """Chave estável quando não há telefone (Telegram, API, etc.)."""
    attrs = blob.get("additional_attributes") if isinstance(blob.get("additional_attributes"), dict) else {}
    for value in (
        blob.get("identifier"),
        blob.get("source_id"),
        attrs.get("social_telegram_user_id"),
        attrs.get("telegram_id"),
        attrs.get("id"),
    ):
        if not value:
            continue
        digits = _digits(value)
        if digits:
            return f"tg{digits}"[:32]
        cleaned = re.sub(r"[^a-zA-Z0-9]", "", str(value))
        if cleaned:
            return f"id{cleaned}"[:32]
    if blob.get("id") is not None:
        try:
            return f"cw{int(blob['id'])}"
        except (TypeError, ValueError):
            pass
    return ""


def _contact_phone(payload: dict) -> str:
    """Telefone real (WhatsApp) ou identidade sintética (Telegram/sem número).

    Sempre tenta devolver uma chave não vazia para o CRM conseguir upsert automático.
    """
    for blob in _contact_blobs(payload):
        phone = _phone_from_blob(blob)
        if phone:
            return phone

    for blob in _contact_blobs(payload):
        identity = _channel_identity_from_blob(blob)
        if identity:
            return identity

    conversation_id = _conversation_id(payload)
    if conversation_id is not None:
        return f"conv{conversation_id}"
    return ""


def _contact_name(payload: dict) -> str:
    for blob in _contact_blobs(payload):
        name = str(blob.get("name") or "").strip()
        if name:
            return name
    return ""


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


def _conversation_custom_attributes(payload: dict) -> dict:
    conversation = payload.get("conversation") or {}
    attrs = conversation.get("custom_attributes")
    return attrs if isinstance(attrs, dict) else {}


def is_handoff_active(payload: dict, *, handoff_label: str | None = None) -> bool:
    attrs = _conversation_custom_attributes(payload)
    flag = attrs.get(HANDOFF_FLAG_ATTR)
    if flag is True or str(flag).lower() in {"true", "1", "yes"}:
        return True
    label = (handoff_label or "").strip().lower()
    if label and any(label == existing.lower() for existing in _conversation_labels(payload)):
        return True
    return False


def _conversation_labels(payload: dict) -> list[str]:
    conversation = payload.get("conversation") or {}
    labels = conversation.get("labels")
    if isinstance(labels, list):
        return [str(label) for label in labels if label]
    if isinstance(labels, str) and labels.strip():
        return [part.strip() for part in labels.split(",") if part.strip()]
    return []


def ignore_reason(payload: dict, *, handoff_label: str | None = None) -> str | None:
    if str(payload.get("event", "")).lower() != "message_created":
        return "not_message_created"

    if _message_type(payload) != "incoming":
        return "not_incoming"

    if is_handoff_active(payload, handoff_label=handoff_label):
        return "handoff_active"

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


def extract_inbound_message(payload: dict, *, handoff_label: str | None = None) -> dict | None:
    if ignore_reason(payload, handoff_label=handoff_label):
        return None

    content = _message_content(payload)
    conversation_id = _conversation_id(payload)
    account_id = _account_id(payload)
    message = payload.get("message") or {}
    message_id = str(payload.get("id") or message.get("id") or "")

    return {
        "phone": _contact_phone(payload),
        "contact_name": _contact_name(payload),
        "chatwoot_contact_id": _contact_chatwoot_id(payload),
        "text": content,
        "conversation_id": conversation_id,
        "account_id": account_id,
        "inbox_id": _inbox_id(payload),
        "message_id": message_id,
        "conversation_status": _conversation_status(payload),
        "raw": payload,
    }


async def send_private_note(
    account_id: int, conversation_id: int, content: str, *, bot_token: str | None = None
) -> dict:
    if not _is_token_configured(bot_token):
        return {"ok": False, "error": "Chatwoot não configurado"}

    url = (
        f"{CHATWOOT_BASE_URL}/api/v1/accounts/{account_id}"
        f"/conversations/{conversation_id}/messages"
    )
    payload = {"content": content, "message_type": "outgoing", "private": True}

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(url, json=payload, headers=_headers(bot_token))
        if response.status_code >= 400:
            return {"ok": False, "error": response.text, "status": response.status_code}
        return {"ok": True, "data": response.json()}


def _token_for_label_api(bot_token: str | None = None) -> str:
    """Prefer admin token — bots em Chatwoot antigo não acessam /labels."""
    return _admin_token() or (bot_token or "").strip() or CHATWOOT_BOT_TOKEN


async def set_conversation_custom_attributes(
    account_id: int,
    conversation_id: int,
    attributes: dict,
    *,
    bot_token: str | None = None,
) -> dict:
    if not _is_token_configured(bot_token):
        return {"ok": False, "error": "Token do robô Chatwoot não configurado para este cliente"}

    url = (
        f"{CHATWOOT_BASE_URL}/api/v1/accounts/{account_id}"
        f"/conversations/{conversation_id}/custom_attributes"
    )
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            url, json={"custom_attributes": attributes}, headers=_headers(bot_token)
        )
        if response.status_code >= 400:
            return {"ok": False, "error": response.text, "status": response.status_code}
        return {"ok": True, "data": response.json()}


async def list_account_labels(account_id: int, *, bot_token: str | None = None) -> dict:
    token = _token_for_account_labels(bot_token)
    if not CHATWOOT_BASE_URL or not token:
        return {"ok": False, "error": "Token admin Chatwoot não configurado"}

    url = f"{CHATWOOT_BASE_URL}/api/v1/accounts/{account_id}/labels"
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(url, headers=_headers(token))
        if response.status_code >= 400:
            return {"ok": False, "error": response.text, "status": response.status_code}
        data = response.json()
        items = data if isinstance(data, list) else data.get("payload", [])
        titles = [str(item.get("title", "")).lower() for item in items if isinstance(item, dict)]
        return {"ok": True, "titles": titles}


async def ensure_account_label(
    account_id: int, label: str, *, bot_token: str | None = None
) -> dict:
    """Garante que a etiqueta existe na conta (requer token de usuário admin)."""
    title = (label or "").strip()
    if not title:
        return {"ok": True, "skipped": True}

    token = _admin_token() or (bot_token or "").strip()
    if not _admin_token():
        # Bot não tem permissão para /accounts/{id}/labels — pular criação automática.
        return {"ok": True, "skipped": True, "reason": "no_admin_token"}

    if not CHATWOOT_BASE_URL or not token:
        return {"ok": False, "error": "CHATWOOT_ADMIN_TOKEN não configurado no servidor"}

    existing = await list_account_labels(account_id, bot_token=token)
    if not existing.get("ok"):
        return existing
    if title.lower() in existing.get("titles", []):
        return {"ok": True, "created": False}

    url = f"{CHATWOOT_BASE_URL}/api/v1/accounts/{account_id}/labels"
    payload = {"title": title, "show_on_sidebar": True}
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(url, json=payload, headers=_headers(token))
        if response.status_code >= 400:
            return {"ok": False, "error": response.text, "status": response.status_code}
        return {"ok": True, "created": True, "data": response.json()}


async def list_conversation_labels(
    account_id: int, conversation_id: int, *, bot_token: str | None = None
) -> dict:
    token = _token_for_label_api(bot_token)
    if not CHATWOOT_BASE_URL or not token:
        return {"ok": False, "error": "Token Chatwoot não configurado"}

    url = (
        f"{CHATWOOT_BASE_URL}/api/v1/accounts/{account_id}"
        f"/conversations/{conversation_id}/labels"
    )
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(url, headers=_headers(token))
        if response.status_code >= 400:
            return {"ok": False, "error": response.text, "status": response.status_code}
        data = response.json()
        payload = data.get("payload", data) if isinstance(data, dict) else data
        labels = [str(label) for label in (payload or []) if label]
        return {"ok": True, "labels": labels}


async def set_conversation_labels(
    account_id: int, conversation_id: int, labels: list[str], *, bot_token: str | None = None
) -> dict:
    token = _token_for_label_api(bot_token)
    if not CHATWOOT_BASE_URL or not token:
        return {"ok": False, "error": "Token Chatwoot não configurado"}

    url = (
        f"{CHATWOOT_BASE_URL}/api/v1/accounts/{account_id}"
        f"/conversations/{conversation_id}/labels"
    )
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(url, json={"labels": labels}, headers=_headers(token))
        if response.status_code >= 400:
            return {"ok": False, "error": response.text, "status": response.status_code}
        return {"ok": True, "data": response.json()}


async def add_conversation_label(
    account_id: int, conversation_id: int, label: str, *, bot_token: str | None = None
) -> dict:
    ensured = await ensure_account_label(account_id, label, bot_token=bot_token)
    if not ensured.get("ok"):
        return ensured

    current = await list_conversation_labels(account_id, conversation_id, bot_token=bot_token)
    if not current.get("ok"):
        direct = await set_conversation_labels(
            account_id, conversation_id, [label.strip()], bot_token=bot_token
        )
        if direct.get("ok"):
            return direct
        return current
    labels = list(current.get("labels") or [])
    normalized = label.strip().lower()
    if not any(existing.lower() == normalized for existing in labels):
        labels.append(label.strip())
    return await set_conversation_labels(account_id, conversation_id, labels, bot_token=bot_token)


async def apply_handoff_markers(
    account_id: int, conversation_id: int, label: str, *, bot_token: str | None = None
) -> dict:
    """Marca handoff: atributo customizado (bot) + etiqueta (admin ou bot recente)."""
    attr_result = await set_conversation_custom_attributes(
        account_id,
        conversation_id,
        {HANDOFF_FLAG_ATTR: True},
        bot_token=bot_token,
    )

    label_result: dict = {"ok": False, "skipped": True}
    title = (label or "").strip()
    if title:
        label_result = await add_conversation_label(
            account_id, conversation_id, title, bot_token=bot_token
        )

    if attr_result.get("ok"):
        return {
            "ok": True,
            "attribute": True,
            "label": bool(label_result.get("ok")),
            "label_error": None if label_result.get("ok") else label_result.get("error"),
        }
    if label_result.get("ok"):
        return {"ok": True, "attribute": False, "label": True}
    return {
        "ok": False,
        "error": attr_result.get("error") or label_result.get("error"),
    }


async def clear_handoff_markers(
    account_id: int,
    conversation_id: int,
    *,
    bot_token: str | None = None,
    handoff_label: str = "",
) -> dict:
    attr_result = await set_conversation_custom_attributes(
        account_id,
        conversation_id,
        {HANDOFF_FLAG_ATTR: False},
        bot_token=bot_token,
    )

    label = (handoff_label or "").strip()
    if label:
        removed = await remove_conversation_label(
            account_id, conversation_id, label, bot_token=bot_token
        )
        if not removed.get("ok") and _admin_token():
            await remove_conversation_label(
                account_id, conversation_id, label, bot_token=_admin_token()
            )

    if not attr_result.get("ok"):
        return attr_result
    return {"ok": True}


async def remove_conversation_label(
    account_id: int, conversation_id: int, label: str, *, bot_token: str | None = None
) -> dict:
    current = await list_conversation_labels(account_id, conversation_id, bot_token=bot_token)
    if not current.get("ok"):
        return current
    labels = [item for item in (current.get("labels") or []) if item.lower() != label.strip().lower()]
    return await set_conversation_labels(account_id, conversation_id, labels, bot_token=bot_token)


async def open_conversation(
    account_id: int, conversation_id: int, *, bot_token: str | None = None
) -> dict:
    """Mantém a conversa visível em Abertas no Chatwoot."""
    return await handoff_conversation(account_id, conversation_id, bot_token=bot_token)


async def handoff_conversation(
    account_id: int, conversation_id: int, *, bot_token: str | None = None
) -> dict:
    if not _is_token_configured(bot_token):
        return {"ok": False, "error": "Chatwoot não configurado"}

    url = (
        f"{CHATWOOT_BASE_URL}/api/v1/accounts/{account_id}"
        f"/conversations/{conversation_id}/toggle_status"
    )
    payload = {"status": "open"}

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(url, json=payload, headers=_headers(bot_token))
        if response.status_code >= 400:
            return {"ok": False, "error": response.text, "status": response.status_code}
        return {"ok": True, "data": response.json()}


async def resume_bot_conversation(
    account_id: int, conversation_id: int, *, bot_token: str | None = None, handoff_label: str = ""
) -> dict:
    """Remove marcadores de handoff e reabre a conversa para o bot voltar a atender."""
    if not _is_token_configured(bot_token):
        return {"ok": False, "error": "Chatwoot não configurado"}

    cleared = await clear_handoff_markers(
        account_id,
        conversation_id,
        bot_token=bot_token,
        handoff_label=handoff_label,
    )
    if not cleared.get("ok"):
        return cleared

    return await open_conversation(account_id, conversation_id, bot_token=bot_token)


async def send_message(
    account_id: int, conversation_id: int, content: str, *, bot_token: str | None = None
) -> dict:
    if not CHATWOOT_BASE_URL:
        return {"ok": False, "error": "CHATWOOT_BASE_URL não configurado no servidor"}
    if not _is_token_configured(bot_token):
        return {
            "ok": False,
            "error": "Token do robô Chatwoot não configurado para este cliente",
        }

    url = (
        f"{CHATWOOT_BASE_URL}/api/v1/accounts/{account_id}"
        f"/conversations/{conversation_id}/messages"
    )
    payload = {"content": content, "message_type": "outgoing", "private": False}

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(url, json=payload, headers=_headers(bot_token))
        if response.status_code >= 400:
            return {"ok": False, "error": response.text, "status": response.status_code}
        return {"ok": True, "data": response.json()}


async def send_attachment(
    account_id: int,
    conversation_id: int,
    *,
    file_path: str,
    filename: str,
    mime_type: str = "application/octet-stream",
    content: str = "",
    bot_token: str | None = None,
) -> dict:
    if not CHATWOOT_BASE_URL:
        return {"ok": False, "error": "CHATWOOT_BASE_URL não configurado no servidor"}
    if not _is_token_configured(bot_token):
        return {
            "ok": False,
            "error": "Token do robô Chatwoot não configurado para este cliente",
        }

    url = (
        f"{CHATWOOT_BASE_URL}/api/v1/accounts/{account_id}"
        f"/conversations/{conversation_id}/messages"
    )
    headers = _headers(bot_token)
    # multipart: não enviar Content-Type json
    headers.pop("Content-Type", None)

    try:
        with open(file_path, "rb") as handle:
            files = {"attachments[]": (filename, handle, mime_type)}
            data = {
                "content": content or filename,
                "message_type": "outgoing",
                "private": "false",
            }
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.post(url, data=data, files=files, headers=headers)
        if response.status_code >= 400:
            return {"ok": False, "error": response.text, "status": response.status_code}
        return {"ok": True, "data": response.json()}
    except Exception as error:
        return {"ok": False, "error": str(error)}


async def send_template(
    account_id: int,
    conversation_id: int,
    template_name: str,
    language: str,
    processed_params: dict,
    content: str = "",
    *,
    bot_token: str | None = None,
) -> dict:
    if not _is_token_configured(bot_token):
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
        response = await client.post(url, json=payload, headers=_headers(bot_token))
        if response.status_code >= 400:
            return {"ok": False, "error": response.text, "status": response.status_code}
        return {"ok": True, "data": response.json()}
