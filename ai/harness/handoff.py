from harness.state import HarnessState
from integrations.chatwoot import add_conversation_label, send_private_note
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
    bot_token = tenant.routing.chatwoot_bot_token
    label = (tenant.handoff.handoff_label or "Atendimento Humano").strip()

    result = await add_conversation_label(
        account_id, conversation_id, label, bot_token=bot_token
    )
    if not result.get("ok"):
        return {
            **state,
            "lifecycle_status": "handoff_failed",
            "handoff_reason": f"{state.get('handoff_reason', '')}: {result.get('error', '')}",
        }

    if tenant.handoff.private_note_enabled:
        note = _build_private_note(state, state.get("handoff_reason", "unknown"))
        await send_private_note(account_id, conversation_id, note, bot_token=bot_token)

    return {
        **state,
        "should_reply": False,
        "outbound_text": "",
        "lifecycle_status": "handed_off",
    }
