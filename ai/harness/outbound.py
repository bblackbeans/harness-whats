import logging

from langchain_core.messages import AIMessage

from harness.state import HarnessState
from integrations.chatwoot import send_message
from tenants import get_tenant

logger = logging.getLogger(__name__)


async def send_reply(state: HarnessState) -> HarnessState:
    if not state.get("should_reply") or not state.get("outbound_text"):
        return {**state, "lifecycle_status": "ignored"}

    tenant = get_tenant(state.get("tenant_id", "default"))
    result = await send_message(
        state["account_id"],
        state["conversation_id"],
        state["outbound_text"],
        bot_token=tenant.routing.chatwoot_bot_token,
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

    return {
        **state,
        "messages": [AIMessage(content=state["outbound_text"])],
        "lifecycle_status": "replied",
    }
