import logging

from handoff.constants import HANDOFF_LABEL
from harness.state import HarnessState
from integrations.chatwoot import add_conversation_label, send_message, send_private_note
from tenants import get_tenant

logger = logging.getLogger(__name__)


def _build_private_note(state: HarnessState, reason: str) -> str:
    return (
        f"[Harness] Handoff para humano\n"
        f"Motivo: {reason}\n"
        f"Intent: {state.get('intent', 'n/a')}\n"
        f"Última mensagem: {state.get('inbound_text', '')[:500]}"
    )


async def execute_handoff(state: HarnessState) -> HarnessState:
    if not state.get("handoff_to_human"):
        return state

    tenant = get_tenant(state.get("tenant_id", "default"))
    if not tenant.handoff.enabled:
        return {**state, "handoff_to_human": False, "lifecycle_status": "ignored"}

    account_id = state["account_id"]
    conversation_id = state["conversation_id"]
    bot_token = tenant.routing.chatwoot_bot_token
    label = HANDOFF_LABEL
    handoff_msg = (tenant.handoff.message or "").strip()
    message_sent = False

    if handoff_msg:
        msg_result = await send_message(
            account_id, conversation_id, handoff_msg, bot_token=bot_token
        )
        if msg_result.get("ok"):
            message_sent = True
        else:
            logger.error(
                "Falha ao enviar mensagem de handoff conv=%s: %s",
                conversation_id,
                msg_result.get("error"),
            )

    result = await add_conversation_label(
        account_id, conversation_id, label, bot_token=bot_token
    )
    if not result.get("ok"):
        error = str(result.get("error", ""))
        logger.error("Falha ao aplicar etiqueta de handoff conv=%s: %s", conversation_id, error)
        hint = (
            "Crie a etiqueta no Chatwoot (Configurações → Etiquetas) "
            f"com o nome exato «{label}»"
        )
        return {
            **state,
            "should_reply": False,
            "outbound_text": handoff_msg if message_sent else "",
            "lifecycle_status": "handoff_failed",
            "handoff_reason": f"{state.get('handoff_reason', '')}: {error}. {hint}",
        }

    if tenant.handoff.private_note_enabled:
        note = _build_private_note(state, state.get("handoff_reason", "unknown"))
        await send_private_note(account_id, conversation_id, note, bot_token=bot_token)

    return {
        **state,
        "should_reply": False,
        "outbound_text": handoff_msg if message_sent else "",
        "lifecycle_status": "handed_off",
    }
