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
        "chatwoot_contact_id": event.chatwoot_contact_id,
        "conversation_id": event.conversation_id,
        "account_id": event.account_id,
        "inbox_id": event.inbox_id,
        "message_id": event.message_id,
        "delivery_id": event.delivery_id,
        "inbound_text": event.text,
        "conversation_summary": "",
        "semantic_facts": [],
        "new_semantic_facts": [],
        "contact_profile": {},
        "field_updates": {},
        "http_tool_calls": [],
        "files_to_send": [],
        "agent_id": None,
        "flow_id": None,
        "flow_run_id": None,
        "agent_system_prompt": "",
        "flow_roteiro": {},
        "flow_checklist": [],
        "flow_checklist_state": {},
        "flow_base_prompt": "",
        "checklist_updates": {},
        "override_agent_id": event.override_agent_id,
        "override_flow_id": event.override_flow_id,
        "allowed_tools": {},
        "transfer_to_agent": None,
        "return_to_orchestrator": False,
        "transfer_rerun": False,
        "transfer_depth": 0,
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
