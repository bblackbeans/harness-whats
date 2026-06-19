from harness.graph import get_graph
from harness.state import HarnessState
from ingress.models import InboundEvent


def _initial_state(event: InboundEvent) -> HarnessState:
    return {
        "messages": [],
        "phone": event.phone,
        "contact_name": event.contact_name,
        "conversation_id": event.conversation_id,
        "account_id": event.account_id,
        "message_id": event.message_id,
        "delivery_id": event.delivery_id,
        "inbound_text": event.text,
        "conversation_summary": "",
        "semantic_facts": [],
        "new_semantic_facts": [],
        "agent_context": "",
        "intent": "",
        "should_reply": False,
        "outbound_text": "",
        "lifecycle_status": "processing",
    }


async def run_conversation_turn(event: InboundEvent) -> HarnessState:
    graph = get_graph()
    config = {"configurable": {"thread_id": f"cw:{event.conversation_id}"}}
    return await graph.ainvoke(_initial_state(event), config)
