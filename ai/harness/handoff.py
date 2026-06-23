from harness.state import HarnessState
from handoff.policy import resolve_handoff
from integrations.chatwoot import handoff_conversation, send_message, send_private_note
from tenants import get_tenant


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
    handoff_message = tenant.handoff.message.strip()
    outbound = state.get("outbound_text", "").strip()

    if handoff_message and outbound != handoff_message:
        if not state.get("should_reply") or not outbound:
            await send_message(account_id, conversation_id, handoff_message)
            state = {**state, "outbound_text": handoff_message, "should_reply": True}

    result = await handoff_conversation(account_id, conversation_id)
    if not result.get("ok"):
        return {
            **state,
            "lifecycle_status": "handoff_failed",
            "handoff_reason": f"{state.get('handoff_reason', '')}: {result.get('error', '')}",
        }

    if tenant.handoff.private_note_enabled:
        note = _build_private_note(state, state.get("handoff_reason", "unknown"))
        await send_private_note(account_id, conversation_id, note)

    return {**state, "lifecycle_status": "handed_off"}
