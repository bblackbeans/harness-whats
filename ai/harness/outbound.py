import logging

from langchain_core.messages import AIMessage

from harness.state import HarnessState
from harness_platform.db import SessionLocal
from harness_platform.sendable_file_service import resolve_sendable_file
from integrations.chatwoot import send_attachment, send_message, open_conversation
from ops.lifecycle import Lifecycle, record_event
from tenants import get_tenant

logger = logging.getLogger(__name__)


def _record_ops(state: HarnessState, status: str, detail: str = "") -> None:
    try:
        record_event(
            delivery_id=str(state.get("delivery_id") or ""),
            message_id=str(state.get("message_id") or ""),
            conversation_id=int(state.get("conversation_id") or 0),
            status=status,
            detail=detail,
            tenant_id=str(state.get("tenant_id") or ""),
            account_id=state.get("account_id"),
            inbox_id=state.get("inbox_id"),
        )
    except Exception:
        logger.exception("Falha ao gravar ops event status=%s", status)


async def send_reply(state: HarnessState) -> HarnessState:
    tenant = get_tenant(state.get("tenant_id", "default"))
    bot_token = tenant.routing.chatwoot_bot_token
    lifecycle = "ignored"

    if state.get("should_reply") and state.get("outbound_text"):
        result = await send_message(
            state["account_id"],
            state["conversation_id"],
            state["outbound_text"],
            bot_token=bot_token,
        )
        if not result.get("ok"):
            logger.error(
                "Falha ao enviar resposta Chatwoot conv=%s: %s",
                state["conversation_id"],
                result.get("error"),
            )
            return {
                **state,
                "lifecycle_status": "send_failed",
                "handoff_reason": str(result.get("error", "send_failed")),
            }
        lifecycle = "replied"

    for ref in state.get("files_to_send") or []:
        db = SessionLocal()
        try:
            resolved = resolve_sendable_file(db, tenant.id, ref)
        finally:
            db.close()
        if not resolved:
            logger.warning("Arquivo para envio não encontrado: %s", ref)
            _record_ops(state, Lifecycle.TOOL_EXECUTED, f"Enviar arquivo '{ref}': não encontrado")
            continue
        row, path = resolved
        attach = await send_attachment(
            state["account_id"],
            state["conversation_id"],
            file_path=str(path),
            filename=row.original_name,
            mime_type=row.mime_type,
            content=f"Segue: {row.original_name}",
            bot_token=bot_token,
        )
        if not attach.get("ok"):
            logger.error("Falha ao enviar arquivo %s: %s", ref, attach.get("error"))
            _record_ops(
                state,
                Lifecycle.TOOL_EXECUTED,
                f"Enviar arquivo '{row.original_name}': erro — {attach.get('error')}",
            )
        else:
            lifecycle = "replied"
            _record_ops(
                state,
                Lifecycle.TOOL_EXECUTED,
                f"Enviar arquivo '{row.original_name}' (#{row.id}): ok",
            )

    if lifecycle == "ignored" and not state.get("outbound_text") and not state.get("files_to_send"):
        return {**state, "lifecycle_status": "ignored"}

    open_result = await open_conversation(
        state["account_id"],
        state["conversation_id"],
        bot_token=bot_token,
    )
    if not open_result.get("ok"):
        logger.warning(
            "Resposta enviada mas falha ao abrir conversa conv=%s: %s",
            state["conversation_id"],
            open_result.get("error"),
        )

    messages = []
    if state.get("outbound_text"):
        messages.append(AIMessage(content=state["outbound_text"]))

    return {
        **state,
        "messages": messages,
        "lifecycle_status": lifecycle,
    }
