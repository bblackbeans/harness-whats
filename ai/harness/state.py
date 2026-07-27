from typing import Annotated, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class HarnessState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    tenant_id: str
    phone: str
    contact_name: str
    chatwoot_contact_id: int | None
    conversation_id: int
    account_id: int
    inbox_id: int | None
    message_id: str
    delivery_id: str
    inbound_text: str
    conversation_summary: str
    semantic_facts: list[str]
    new_semantic_facts: list[str]
    contact_profile: dict
    field_updates: dict
    http_tool_calls: list[str]
    files_to_send: list[str]
    agent_id: int | None
    flow_id: int | None
    flow_run_id: int | None
    agent_system_prompt: str
    flow_roteiro: dict
    flow_checklist: list
    flow_checklist_state: dict
    flow_base_prompt: str
    checklist_updates: dict
    override_agent_id: int | None
    override_flow_id: int | None
    allowed_tools: dict
    transfer_to_agent: object
    return_to_orchestrator: bool
    transfer_rerun: bool
    transfer_depth: int
    agent_context: str
    retrieved_knowledge: list[str]
    handoff_to_human: bool
    handoff_reason: str
    intent: str
    should_reply: bool
    outbound_text: str
    lifecycle_status: str
