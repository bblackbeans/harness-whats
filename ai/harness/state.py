from typing import Annotated, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class HarnessState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    tenant_id: str
    phone: str
    contact_name: str
    conversation_id: int
    account_id: int
    inbox_id: int | None
    message_id: str
    delivery_id: str
    inbound_text: str
    conversation_summary: str
    semantic_facts: list[str]
    new_semantic_facts: list[str]
    agent_context: str
    retrieved_knowledge: list[str]
    handoff_to_human: bool
    handoff_reason: str
    intent: str
    should_reply: bool
    outbound_text: str
    lifecycle_status: str
