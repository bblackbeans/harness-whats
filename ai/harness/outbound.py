from langchain_core.messages import AIMessage

from harness.state import HarnessState
from integrations.chatwoot import send_message


async def send_reply(state: HarnessState) -> HarnessState:
    if not state.get("should_reply") or not state.get("outbound_text"):
        return {**state, "lifecycle_status": "ignored"}

    await send_message(state["account_id"], state["conversation_id"], state["outbound_text"])
    return {
        **state,
        "messages": [AIMessage(content=state["outbound_text"])],
        "lifecycle_status": "replied",
    }
