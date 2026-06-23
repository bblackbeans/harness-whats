from harness.graph import get_graph
from harness.state import HarnessState
from ingress.models import InboundEvent
from tenants import resolve_tenant


def _initial_state(event: InboundEvent) -> HarnessState:
    tenant = resolve_tenant(event)
    return {
        "messages": [],
        "tenant_id": tenant.id,
        "phone": event.phone,
        "contact_name": event.contact_name,
        "conversation_id": event.conversation_id,
        "account_id": event.account_id,
        "inbox_id": event.inbox_id,
        "message_id": event.message_id,
        "delivery_id": event.delivery_id,
        "inbound_text": event.text,
        "conversation_summary": "",
        "semantic_facts": [],
        "new_semantic_facts": [],
        "agent_context": "",
        "retrieved_knowledge": [],
        "handoff_to_human": False,
        "handoff_reason": "",
        "intent": "",
        "should_reply": False,
        "outbound_text": "",
        "lifecycle_status": "processing",
    }


async def run_conversation_turn(event: InboundEvent) -> HarnessState:
    graph = get_graph()
    tenant = resolve_tenant(event)
    config = {"configurable": {"thread_id": f"{tenant.id}:cw:{event.conversation_id}"}}
    return await graph.ainvoke(_initial_state(event), config)
